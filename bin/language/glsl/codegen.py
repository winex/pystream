# Copyright 2011 Nicholas Bray
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from util.typedispatch import *
from . import ast

from . import codecollapser

class TypeNameGen(TypeDispatcher):
	@dispatch(ast.BuiltinType)
	def visitBuiltinType(self, node):
		return node.name

	@dispatch(ast.StructureType)
	def visitStructureType(self, node):
		return node.name

	@dispatch(ast.ArrayType)
	def visitArrayType(self, node):
		return "%s[%d]" % (self(node.type), node.count)


class FindLocals(TypeDispatcher):
	@defaultdispatch
	def visitOK(self, node):
		node.visitChildren(self)

	@dispatch(list, tuple)
	def visitContainer(self, node):
		for child in node:
			self(child)

	@dispatch(str, int, type(None))
	def visitLeaf(self, node):
		pass

	@dispatch(ast.Local)
	def visitLocal(self, node):
		self.locals.add(node)

	@dispatch(ast.Uniform)
	def visitUniform(self, node):
		self.uniforms.add(node.decl)

	@dispatch(ast.Input)
	def visitInput(self, node):
		self.inputs.add(node.decl)

	@dispatch(ast.Output)
	def visitOutput(self, node):
		self.outputs.add(node.decl)


	def processCode(self, node):
		self.locals = set()
		self(node.params)
		parameters = self.locals

		self.locals   = set()
		self.uniforms = set()
		self.inputs   = set()
		self.outputs  = set()

		self(node.body)
		return self.locals-parameters

class GLSLCodeGen(TypeDispatcher):
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

	def wrapSimpleStatement(self, s, prec=None, container=None):
		return "%s%s;\n" % (self.indent, s)

	@dispatch(ast.VariableDecl)
	def visitVariableDecl(self, node):
		initialize = '' if node.initializer is None else (" = " +self(node.initializer))
		return self.wrapSimpleStatement("%s %s%s" % (self.typename(node.type), node.name, initialize))

	@dispatch(ast.UniformDecl)
	def visitUniformDecl(self, node):
		initialize = '' if node.initializer is None else (" = " +self(node.initializer))
		stmt = "uniform %s %s%s" % (self.typename(node.type), node.name, initialize)
		if node.builtin: stmt = "//" + stmt
		return stmt

	@dispatch(ast.StructureType)
	def visitStructureType(self, node):
		oldIndent = self.indent
		self.indent += '\t'
		statements = ["%s%s;\n" % (self.indent, self(field)) for field in node.fieldDecl]
		self.indent = oldIndent
		body = "".join(statements)
		return "{indent}struct {name}\n{indent}{{\n{body}{indent}}};\n".format(indent=self.indent, name=node.name, body=body)

	@dispatch(ast.BuiltinType)
	def visitBuiltinType(self, node):
		return "{indent}{name};\n".format(indent=self.indent, name=node.name)

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


	@dispatch(ast.GetSubscript)
	def visitGetSubscript(self, node, prec=17):
		return self.wrap("%s[%s]" % (self(node.expr, 1), self(node.subscript, 2)), 2, prec)

	@dispatch(ast.SetSubscript)
	def visitSetSubscript(self, node, prec=17):
		return self.wrapSimpleStatement("%s[%s] = %s" % (self(node.expr, 15), self(node.subscript, 16), self(node.value, 16)), 16, prec)


	@dispatch(ast.BinaryOp)
	def visitBinaryOp(self, node, prec=17):
		opPrec = self.precedenceLUT[node.op]
		return self.wrap("%s%s%s" % (self(node.left, opPrec), node.op, self(node.right, opPrec-1)), opPrec, prec)

	@dispatch(ast.UnaryPrefixOp)
	def visitUnaryPrefixOp(self, node, prec=17):
		return self.wrap("%s%s" % (node.op, self(node.expr, 2)), 2, prec)

	@dispatch(ast.ShortCircutAnd)
	def visitShortCircutAnd(self, node, prec=17):
		opPrec = 11
		# TODO precedence on first element wrong?
		exprs = [self(expr, opPrec-1) for expr in node.exprs]
		s = " && ".join(exprs)
		return self.wrap(s, opPrec, prec)

	@dispatch(ast.ShortCircutOr)
	def visitShortCircutOr(self, node, prec=17):
		opPrec = 12
		# TODO precedence on first element wrong?
		exprs = [self(expr, opPrec-1) for expr in node.exprs]
		s = " || ".join(exprs)
		return self.wrap(s, opPrec, prec)



	@dispatch(ast.Assign)
	def visitAssign(self, node, prec=17):
		return self.wrapSimpleStatement("%s = %s" % (self(node.lcl, 15), self(node.expr, 16)), 16, prec)

	@dispatch(ast.Store)
	def visitStore(self, node, prec=17):
		return self.wrapSimpleStatement("%s.%s = %s" % (self(node.expr, 1), node.name, self(node.value, 16)), 16, prec)

	@dispatch(ast.Discard)
	def visitDiscard(self, node, prec=17):
		return self.wrapSimpleStatement(self(node.expr, 16), 16, prec)

	def newLocalName(self, base):
		name = '%s_%d' % (base, self.uid)
		self.uid += 1
		return name

	def uniqueName(self, basename):
		name     = basename

		if name is None:
			basename = ''
			name = self.newLocalName(basename)

		while name in self.localNames:
			name = self.newLocalName(basename)

		self.localNames.add(name)

		return name

	@dispatch(ast.Local)
	def visitLocal(self, node, prec=17):
		if node not in self.localNameLUT:
			name = self.uniqueName(node.name)
			self.localNameLUT[node] = name
		else:
			name = self.localNameLUT[node]
		return name


	@dispatch(ast.Uniform)
	def visitUniform(self, node, prec=17):
		return self.visitLocal(node.decl)

	@dispatch(ast.Input)
	def visitInput(self, node, prec=17):
		return self.visitLocal(node.decl)

	@dispatch(ast.Output)
	def visitOutput(self, node, prec=17):
		return self.visitLocal(node.decl)

	@dispatch(ast.Return)
	def visitReturn(self, node):
		if node.expr is None:
			return self.wrapSimpleStatement("return")
		else:
			return self.wrapSimpleStatement("return %s" % self(node.expr))

	def canFlattenSwitch(self, suite):
		return len(suite.statements) == 1 and isinstance(suite.statements[0], ast.Switch)

	@dispatch(ast.Switch)
	def visitSwitch(self, node):
		condition = self(node.condition)

		t = self(node.t)
		s = "%sif(%s)\n%s{\n%s%s}\n" % (self.indent, condition, self.indent, t, self.indent,)

		elseBlock = node.f

		while True:
			if self.canFlattenSwitch(elseBlock):
				switch = elseBlock.statements[0]
				condition = self(switch.condition)
				t = self(switch.t)
				s += "%selse if(%s)\n%s{\n%s%s}\n" % (self.indent, condition, self.indent, t, self.indent,)
				elseBlock = switch.f
			else:
				if len(elseBlock.statements):
					f = self(elseBlock)
					s += "%selse\n%s{\n%s%s}\n" % (self.indent, self.indent, f, self.indent)
				break

		return s

	@dispatch(ast.While)
	def visitWhile(self, node):
		condition = self(node.condition)

		body = self(node.body)
		s = "%swhile(%s)\n%s{\n%s%s}\n" % (self.indent, condition, self.indent, body, self.indent,)

		return s

	@dispatch(ast.Suite)
	def visitSuite(self, node):
		oldIndent = self.indent
		self.indent += '\t'
		#statements = ["%s%s;\n" % (self.indent, self(stmt)) for stmt in node.statements]
		statements = [self(stmt) for stmt in node.statements]
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

	@dispatch(ast.InputDecl)
	def visitInputDecl(self, node):
		stmt = "in %s %s" % (self.typename(node.type), self.visitLocal(node))
		if node.builtin: stmt = "//" + stmt
		return stmt


	@dispatch(ast.OutputDecl)
	def visitOutputDecl(self, node):
		stmt = "out %s %s" % (self.typename(node.type), self.visitLocal(node))
		if node.builtin: stmt = "//" + stmt
		return stmt


	def makeLocalDecl(self, lcls):
		decl = "".join(["\t%s %s;\n" % (self.typename(lcl.type), self(lcl)) for lcl in lcls])
		return decl

	def makeDecl(self, lcls):
		decl = "".join(["%s;\n" % (self(lcl)) for lcl in lcls])
		return decl

	@dispatch(ast.BlockDecl)
	def visitBlockDecl(self, node):
		if node.layout:
			layout = "layout(%s) " % node.layout
		else:
			layout = ""




		oldIndent = self.indent
		self.indent += '\t'
		statements = ["%s%s;\n" % (self.indent, self(stmt)) for stmt in node.decls]
		self.indent = oldIndent
		body = "".join(statements)

		stmt = "%suniform %s\n{\n%s}" % (layout, node.name, body)

		return stmt

	@dispatch(ast.Declarations)
	def visitDeclarations(self, node):
		decl = "".join(["%s;\n" % (self(decl)) for decl in node.decls])
		return decl


	@dispatch(ast.Code)
	def visitCode(self, node, uniblock):
		finder = FindLocals()
		finder.processCode(node)

		# Generate header declarations
		parts = ["#version 150\n"]

		if uniblock:
			parts.append(self(uniblock))
		else:
			uniformdecl = self.makeDecl(finder.uniforms)
			if uniformdecl: parts.append(uniformdecl)

			outputdecl  = self.makeDecl(finder.outputs)
			if outputdecl: parts.append(outputdecl)

		inputdecl   = self.makeDecl(finder.inputs)
		if inputdecl: parts.append(inputdecl)

		header = "\n".join(parts)

		# Generate local declarations
		localdecl = self.makeLocalDecl(finder.locals)

		return "%s\n%s %s(%s)\n{\n%s\n%s}\n" % (header, self.typename(node.returnType), node.name, ", ".join([self(param) for param in node.params]), localdecl, self(node.body))

def evaluateCode(compiler, code, uniblock=None):
	code = codecollapser.evaluateCode(compiler, code)
	return GLSLCodeGen()(code, uniblock)
