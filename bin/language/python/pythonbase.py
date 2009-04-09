from language.base.metaast import *
from . import annotations

def isPythonAST(ast):
	return isinstance(ast, PythonASTNode)

class PythonASTNode(ASTNode):
	def returnsValue(self):
		return False

	def isPure(self):
		return False

	def isControlFlow(self):
		return False

	def isReference(self):
		return False

class Expression(PythonASTNode):
	__slots__ = ()

	emptyAnnotation = annotations.emptyOpAnnotation

	def returnsValue(self):
		return True

class LLExpression(Expression):
	__slots__ = ()

	def returnsValue(self):
		return True

class Reference(Expression):
	__slots__ = ()

	emptyAnnotation = annotations.emptySlotAnnotation

	def isReference(self):
		return True

class Statement(PythonASTNode):
	__slots__ = ()

	emptyAnnotation = annotations.emptyOpAnnotation

class SimpleStatement(Statement):
	__slots__ = ()

class LLStatement(SimpleStatement):
	__slots__ = ()

class ControlFlow(SimpleStatement):
	__slots__ = ()

	def significant(self):
		return True

	def isControlFlow(self):
		return True

class CompoundStatement(Statement):
	__slots__ = ()

	def significant(self):
		return True
