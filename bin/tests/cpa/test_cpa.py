from __future__ import absolute_import
import unittest

import analysis.cpa
import common.makefile
from decompiler.programextractor import extractProgram


from common.compilerconsole import CompilerConsole
from common.compilercontext import CompilerContext

from decompiler.programextractor import Extractor
from util import replaceGlobals

class TestCPA(unittest.TestCase):
	def assertIn(self, first, second, msg=None):
		"""Fail if the one object is not in the other, using the "in" operator.
		"""
		if first not in second:
			raise self.failureException, (msg or '%r not in %r' % (first, second))

	def assertLocalRefTypes(self, lcl, types):
		refs   = lcl.annotation.references[0]

		# There's one reference returned, and it's an integer.
		self.assertEqual(len(refs), len(types))
		for ref in refs:
			self.assertIn(ref.xtype.obj.type, types)

	def testAdd(self):
		def func(a, b):
			return 2*a+b

		# Prevent leakage?
		func = replaceGlobals(func, {})

		# TODO mock console?
		compiler = CompilerContext(CompilerConsole())

		interface = common.makefile.InterfaceDeclaration()

		interface.func.append((func,
			(common.makefile.ExistingWrapper(3), common.makefile.ExistingWrapper(5))
			))

		compiler.interface = interface

		extractProgram(compiler)
		result = analysis.cpa.evaluate(compiler)

		# Check argument and return types
		funcobj, funcast = compiler.extractor.getObjectCall(func)
		types = set([compiler.extractor.getObject(int)])

		for param in funcast.codeparameters.params:
			self.assertLocalRefTypes(param, types)

		for param in funcast.codeparameters.returnparams:
			self.assertLocalRefTypes(param, types)