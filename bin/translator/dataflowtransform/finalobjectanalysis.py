from util.typedispatch import *
import analysis.dataflowIR.traverse
from analysis.dataflowIR import graph

class FinalObjectAnalysis(TypeDispatcher):
	def __init__(self, compiler, dataflow):
		TypeDispatcher.__init__(self)
		self.compiler = compiler
		self.dataflow = dataflow

		self.nonfinal = set()
		self.objects  = set()

	@dispatch(graph.Entry, graph.Exit, graph.PredicateNode, graph.Gate,
	graph.NullNode, graph.Split, graph.Merge,)
	def visitJunk(self, node):
		pass

	@dispatch(graph.FieldNode,)
	def visitField(self, node):
		# TODO is this necessary?
		node = node.canonical()
		self.objects.update(node.annotation.values.flat)

	@dispatch(graph.LocalNode, graph.ExistingNode,)
	def visitSlot(self, node):
		node = node.canonical()
		self.objects.update(node.annotation.values.flat)

	@dispatch(graph.GenericOp)
	def visitOp(self, node):
		alloc = node.annotation.allocate.flat
		mod   = node.annotation.modify.flat

		# Find
		for slot in mod:
			field = slot.name
			obj   = field.object
			if obj not in alloc:
				self.nonfinal.add(obj)

	def process(self):
		# Analyze
		analysis.dataflowIR.traverse.dfs(self.dataflow, self)

		# Annotate
		for obj in self.objects:
			final = obj not in self.nonfinal
			obj.annotation = obj.annotation.rewrite(final=final)

		if False:
			print "=== Objects ==="
			for obj in self.objects:
				print obj
				print obj.annotation
				print



def process(compiler, dataflow):
	foa = FinalObjectAnalysis(compiler, dataflow)
	foa.process()
