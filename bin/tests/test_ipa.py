import unittest

from analysis.ipa.ipanalysis import IPAnalysis
from analysis.ipa.constraints import flow, qualifiers

from language.python import program

from analysis.storegraph.canonicalobjects import CanonicalObjects

class MockExtractor(object):
	def __init__(self):
		self.cache = {}

	def getObject(self, pyobj):
		key = (type(pyobj), pyobj)
		result = self.cache.get(key)
		if result is None:
			result = program.Object(pyobj)
			self.cache[key] = result
		return result

class MockSignature(object):
	def __init__(self):
		self.code = None

class TestConstraintBase(unittest.TestCase):
	def setUp(self):
		self.extractor = MockExtractor()
		self.canonical = CanonicalObjects()
		existingPolicy = None
		externalPolicy = None

		self.analysis = IPAnalysis(self.extractor, self.canonical, existingPolicy, externalPolicy)
	
	def local(self, context, name, *values):
		lcl = context.local(name)
		if values: lcl.updateValues(frozenset(values))
		return lcl

	def assertIsInstance(self, obj, cls):
		self.assert_(isinstance(obj, cls), "expected %r, got %r" % (cls, type(obj)))

	def const(self, pyobj, qualifier=qualifiers.HZ):
		obj = self.extractor.getObject(pyobj)
		xtype = self.canonical.existingType(obj)
		return self.analysis.objectName(xtype, qualifier)

class TestFlowConstraints(TestConstraintBase):
	def setUp(self):
		TestConstraintBase.setUp(self)
		self.context  = self.analysis.getContext(MockSignature())

	def testStore(self):
		o = self.const('obj')
		n = self.const('name')
		v = self.const('value')

		src       = self.local(self.context, 0, v)
		dst       = self.local(self.context, 1, o)
		fieldtype = 'Attribute'
		fieldname = self.local(self.context, 2, n)

		self.context.constraint(flow.StoreConstraint(src, dst, fieldtype, fieldname))

		# Check that a constraint was created
		self.assertEqual(len(self.context.constraints), 2)
		concrete = self.context.constraints[1]
		self.assertIsInstance(concrete, flow.CopyConstraint)

		field = concrete.dst

		# Check that the target is the right field
		self.assertEqual(field, self.context.field(o, fieldtype, n.obj()))

		# Check that the value propagated
		self.assertEqual(field.values, frozenset([v]))


	def testLoad(self):
		o = self.const('obj')
		n = self.const('name')
		v = self.const('value')

		src       = self.local(self.context, 0, o)
		fieldtype = 'Attribute'
		fieldname = self.local(self.context, 1, n)
		dst       = self.local(self.context, 2)

		field = self.context.field(o, fieldtype, n.obj())
		field.updateSingleValue(v)

		self.context.constraint(flow.LoadConstraint(src, fieldtype, fieldname, dst))

		# Check that a constraint was created
		self.assertEqual(len(self.context.constraints), 2)
		concrete = self.context.constraints[1]
		self.assertIsInstance(concrete, flow.CopyConstraint)

		# Check that the source is the right field
		self.assertEqual(concrete.src, field)

		# Check that the value propagated
		self.assertEqual(dst.values, field.values)


	def checkTemplate(self, value, null):
		o = self.const('obj')
		n = self.const('name')
		v = self.const('value')

		src       = self.local(self.context, 0, o)
		fieldtype = 'Attribute'
		fieldname = self.local(self.context, 1, n)
		dst       = self.local(self.context, 2)

		field = self.context.field(o, fieldtype, n.obj())
		self.assertEqual(field.null, True)

		if not null: field.clearNull()
		if value: field.updateSingleValue(v)

		self.context.constraint(flow.CheckConstraint(src, fieldtype, fieldname, dst))

		# Check that a constraint was created
		self.assertEqual(len(self.context.constraints), 2)
		concrete = self.context.constraints[1]
		self.assertIsInstance(concrete, flow.ConcreteCheckConstraint)

		# Check that the source is the right field
		self.assertEqual(concrete.src, field)

		expected = []
		if null: expected.append(self.context.allocatePyObj(False))
		if value: expected.append(self.context.allocatePyObj(True))

		# Check that the value propagated
		self.assertEqual(dst.values, frozenset(expected))


	def testCheckBoth(self):
		self.checkTemplate(True, True)

	def testCheckValue(self):
		self.checkTemplate(True, False)

	def testCheckNull(self):
		self.checkTemplate(False, True)

	def testCheckNeither(self):
		self.checkTemplate(False, False)


class TestDownwardFieldTransfer(TestConstraintBase):
	def setUp(self):
		TestConstraintBase.setUp(self)

		self.contextA  = self.analysis.getContext(MockSignature())
		self.contextB  = self.analysis.getContext(MockSignature())
		self.contextC  = self.analysis.getContext(MockSignature())


	def testNewTransfer(self):
		o = self.const('obj', qualifiers.HZ)
		od = self.const('obj', qualifiers.DN)
		n = self.const('name')
		v = self.const('value')
		fieldtype = 'Attribute'

		slotA = self.contextA.field(o, fieldtype, n.obj())
		slotA.updateSingleValue(v)
		
		invokeAB = self.contextA.getInvoke(None, self.contextB)
		
		# Copy down before field is created
		remapped = invokeAB.copyDown(o)
		self.assertEqual(remapped, od)
		
		slotB = self.contextB.field(od, fieldtype, n.obj())
		
		expected = frozenset([invokeAB.objForward[value] for value in slotA.values])
		self.assertEqual(slotB.values, expected)
	
	def testOldTransfer(self):
		o = self.const('obj', qualifiers.HZ)
		od = self.const('obj', qualifiers.DN)
		n = self.const('name')
		v = self.const('value')
		fieldtype = 'Attribute'

		slotA = self.contextA.field(o, fieldtype, n.obj())
		slotA.updateSingleValue(v)
		
		invokeAB = self.contextA.getInvoke(None, self.contextB)
		
		slotB = self.contextB.field(od, fieldtype, n.obj())

		self.assertEqual(slotB.values, frozenset())

		# Copy down after field is created
		remapped = invokeAB.copyDown(o)
		self.assertEqual(remapped, od)
		
		expected = frozenset([invokeAB.objForward[value] for value in slotA.values])
		self.assertEqual(slotB.values, expected)
	
	def testMultiTransfer(self):
		o = self.const('obj', qualifiers.HZ)
		od = self.const('obj', qualifiers.DN)
		n  = self.const('name')
		v1 = self.const('value1')
		v2 = self.const('value2')
		v3 = self.const('value3')

		fieldtype = 'Attribute'

		slotA = self.contextA.field(o, fieldtype, n.obj())
		slotA.updateSingleValue(v1)
		slotA.updateSingleValue(v2)

		slotB = self.contextB.field(o, fieldtype, n.obj())
		slotB.updateSingleValue(v2)
		slotB.updateSingleValue(v3)

		
		invokeAC = self.contextA.getInvoke(None, self.contextC)
		invokeBC = self.contextB.getInvoke(None, self.contextC)
		
		slotC = self.contextC.field(od, fieldtype, n.obj())

		self.assertEqual(slotC.values, frozenset())

		# Copy down after field is created
		remapped = invokeAC.copyDown(o)
		self.assertEqual(remapped, od)

		remapped = invokeBC.copyDown(o)
		self.assertEqual(remapped, od)

		expectedA = [invokeAC.objForward[value] for value in slotA.values]
		self.assertEqual(len(expectedA), 2)
		
		expectedB = [invokeBC.objForward[value] for value in slotB.values]
		self.assertEqual(len(expectedB), 2)
		
		expected = frozenset(expectedA+expectedB)
		self.assertEqual(len(expected), 3)
		
		self.assertEqual(slotC.values, expected)
	
	def testChainTransfer(self):
		o = self.const('obj', qualifiers.HZ)
		od = self.const('obj', qualifiers.DN)
		n  = self.const('name')
		v1 = self.const('value1')
		v2 = self.const('value2')
		v3 = self.const('value3')

		fieldtype = 'Attribute'

		slotA = self.contextA.field(o, fieldtype, n.obj())
		slotA.updateSingleValue(v1)
		slotA.updateSingleValue(v2)

		slotB = self.contextB.field(o, fieldtype, n.obj())
		slotB.updateSingleValue(v2)
		slotB.updateSingleValue(v3)

		
		invokeAB = self.contextA.getInvoke(None, self.contextB)
		invokeBC = self.contextB.getInvoke(None, self.contextC)
		
		slotC = self.contextC.field(od, fieldtype, n.obj())

		self.assertEqual(slotC.values, frozenset())


		remapped = invokeBC.copyDown(o)
		self.assertEqual(remapped, od)

		# At this point A has NOT been coppied all the way down to C.
		expected = frozenset([invokeBC.objForward[value] for value in slotB.values])
		self.assertEqual(len(expected), 2)
		self.assertEqual(slotC.values, expected)

		# Copy down after field is created
		remapped = invokeAB.copyDown(o)
		self.assertEqual(remapped, od)

		self.assertEqual(len(slotB.values), 2)

		# Finish propagation		
		invokeBC.copyDown(remapped)

		self.assertEqual(len(slotB.values), 2)
		self.assertEqual(len(slotC.values), 3)
