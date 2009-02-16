import os.path
import pydot
import util.graphalgorithim.dominator
from analysis.astcollector import getOps

# HACK duplicated code
def codeShortName(code):
	if isinstance(code, str):
		name = func
		args = []
		vargs = None
		kargs = None
	elif code is None:
		name = 'external'
		args = []
		vargs = None
		kargs = None
	else:
		name = code.name
		args = list(code.parameternames)
		vargs = None if code.vparam is None else code.vparam.name
		kargs = None if code.kparam is None else code.kparam.name

	if vargs is not None: args.append("*"+vargs)
	if kargs is not None: args.append("**"+kargs)

	return "%s(%s)" % (name, ", ".join(args))


def dumpGraph(name, g, format='svg', prog='dot'):
	s = g.create(prog=prog, format=format)
	fn = name+('.'+format)
	f = open(fn, 'wb')
	f.write(s)
	f.close()
	return fn

def dump(data, entryPoints, links, reportDir):
	# Find live functions
	stack = []
	processed = set()

	head = None
	invokeLUT = {}
	invokeLUT[head] = set()

	# Process the entry points
	for code, funcobj, args in entryPoints:
		for context in code.annotation.contexts:
			context = None
			invokeLUT[head].add(code)
			key = (code, context)
			if key not in processed:
				stack.append(key)
				processed.add(key)

	# Find live invocations
	while stack:
		node =  stack.pop()
		code, context = node
		ops, lcls = getOps(code)

		invokeLUT[code] = set()

		for op in ops:
			invokes = op.annotation.invokes
			if invokes is not None:
				if context is None:
					cinvokes = invokes[0]
				else:
					cindex = code.annotation.contexts.index(context)
					cinvokes = invokes[1][cindex]

				for f, c in cinvokes:
					c = None
					key = (f, c)
					invokeLUT[code].add(f)
					if key not in processed:
						stack.append(key)
						processed.add(key)

	# Make dominator tree
	tree, idoms = util.graphalgorithim.dominator.dominatorTree(invokeLUT, head)

	# Start graph creation
	g = pydot.Dot(graph_type='digraph',
			#overlap='scale',
			rankdir='LR',
			#concentrate=True,
			)

	# Create nodes
	def makeNode(tree, sg, node):
		if node is not None:
			code = node

			if code.annotation.descriptive:
				nodecolor = "#FF3333"
			elif code.selfparam is None:
				nodecolor = '#BBBBBB'
			else:
				nodecolor = '#33FF33'
			sg.add_node(pydot.Node(str(id(node)), label=codeShortName(code),
				shape='box', style="filled", fontsize=8,
				fillcolor=nodecolor, URL=links.codeRef(node, None)))


		children = tree.get(node)
		if children:
			csg = pydot.Cluster(str(id(node)))
			sg.add_subgraph(csg)
			for child in children:
				makeNode(tree, csg, child)

	makeNode(tree, g, head)

	# Create edges
	for src, dsts in invokeLUT.iteritems():
		if src is head: continue
		for dst in dsts:
			if idoms.get(dst) is src:
				weight = 10
			else:
				weight = 1
			g.add_edge(pydot.Edge(str(id(src)), str(id(dst)), weight=weight))

	# Output
	dumpGraph(os.path.join(reportDir, 'invocations'), g, prog='dot')