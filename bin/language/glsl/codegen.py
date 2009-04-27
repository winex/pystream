from util.typedispatch import *
from . import ast

class TypeNameGen(StrictTypeDispatcher):
	@dispatch(ast.BuiltinType)
	def visitBuiltinType(self, node):
		return node.name

	@dispatch(ast.StructureType)
	def visitStructureType(self, node):
		return node.name

	@dispatch(ast.ArrayType)
	def visitArrayType(self, node):
		return "%s[%d]" % (self(node.type), node.count)


class FindLocals(StrictTypeDispatcher):
	@defaultdispatch
	def visitOK(self, node):
		visitAllChildren(self, node)

	@dispatch(ast.Local)
	def visitLocal(self, node):
		self.locals.add(node)

	def processCode(self, node):
		self.locals = set()
		self(node.parameters)
		parameters = self.locals

		self.locals = set()
		self(node.body)
		return self.locals-parameters

class GLSLCodeGen(StrictTypeDispatcher):
	precedenceLUT = {'*':4, '/':4, '%':4, '+':5, '-':5, '<<':6, '>>':6,
		'<':7, '>':7, '>=':7, '<=':7, '==':8, '!=':8,
		'&':9, '^':10, '|':11, '&&':12, '^^':13, '||':14}

	def __init__(self):
		# Changes depending on the shader and the language target.
		self.inLabel  = 'in'
		self.outLabel = 'out'

		self.typename = TypeNameGen()

		self.indent = ''

		self.localNameLUT = {}
		self.localNames   = set()
		self.uid = 0

	def wrap(self, s, prec, container):
		if prec > container:
			return "(%s)" % s
		else:
			return s

	@dispatch(ast.VariableDecl)
	def visitVariableDecl(self, node):
		initialize = '' if node.initializer is None else (" = " +self(node.initializer))
		return "%s %s%s" % (self.typename(node.type), node.name, initialize)

	@dispatch(ast.UniformDecl)
	def visitUniformDecl(self, node):
		initialize = '' if node.initializer is None else (" = " +self(node.initializer))
		return "uniform %s %s%s" % (self.typename(node.type), node.name, initialize)


	@dispatch(ast.Constant)
	def visitConstant(self, node, prec=17):
		if isinstance(node, str):
			return repr(node)
		else:
			return str(node.object)

	@dispatch(ast.Constructor)
	def visitConstructor(self, node, prec=17):
		typename = self.typename(node.type)
		assert isinstance(typename, str), node
		return self.wrap("%s(%s)" % (typename, ", ".join([self(arg) for arg in node.args])), 2, prec)

	@dispatch(ast.IntrinsicOp)
	def visitIntrinsicOp(self, node, prec=17):
		return self.wrap("%s(%s)" % (node.name, ", ".join([self(arg) for arg in node.args])), 2, prec)

	@dispatch(ast.Load)
	def visitLoad(self, node, prec=17):
		return self.wrap("%s.%s" % (self(node.expr, 1), node.name), 2, prec)


	@dispatch(ast.BinaryOp)
	def visitBinaryOp(self, node, prec=17):
		opPrec = self.precedenceLUT[node.op]
		return self.wrap("%s%s%s" % (self(node.left, opPrec), node.op, self(node.right, opPrec-1)), opPrec, prec)

	@dispatch(ast.Assign)
	def visitAssign(self, node, prec=17):
		return self.wrap("%s = %s" % (self(node.lcl, 15), self(node.expr, 16)), 16, prec)

	@dispatch(ast.Discard)
	def visitDiscard(self, node, prec=17):
		return self.wrap(self(node.expr, 16), 16, prec)

	def newLocalName(self, base):
		name = '%s_%d' % (base, self.uid)
		self.uid += 1
		return name

	@dispatch(ast.Local)
	def visitLocal(self, node, prec=17):
		if node not in self.localNameLUT:
			basename = node.name
			name     = basename

			if name is None:
				basename = ''
				name = self.newLocalName(basename)

			while name in self.localNames:
				name = self.newLocalName(basename)

			self.localNameLUT[node] = name
			self.localNames.add(name)
		else:
			name = self.localNameLUT[node]

		return name

	@dispatch(ast.Return)
	def visitReturn(self, node):
		if node.expr is None:
			return "return"
		else:
			return "return %s" % self(node.expr)

	@dispatch(ast.Suite)
	def visitSuite(self, node):
		oldIndent = self.indent
		self.indent += '\t'
		statements = ["%s%s;\n" % (self.indent, self(stmt)) for stmt in node.statements]
		self.indent = oldIndent
		return "".join(statements)

	@dispatch(ast.Parameter)
	def visitParameter(self, node):
		prefix = ''
		if node.paramIn:
			prefix += 'in'
		if node.paramOut:
			prefix += 'out'

		return '%s %s %s' % (prefix, self.typename(node.lcl.type), node.lcl.name)

	def makeDecl(self, node):
		lcls = FindLocals().processCode(node)
		decl = "".join(["\t%s %s;\n" % (self.typename(lcl.type), self(lcl)) for lcl in lcls])
		return decl

	@dispatch(ast.Code)
	def visitCode(self, node):
		decl = self.makeDecl(node)

		return "%s %s(%s)\n{\n%s\n%s}\n" % (self.typename(node.returnType), node.name, ", ".join([self(param) for param in node.parameters]), decl, self(node.body))