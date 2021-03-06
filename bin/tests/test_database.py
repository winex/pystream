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

from __future__ import absolute_import

import unittest


import analysis.lifetimeanalysis.database.structure as structure
import analysis.lifetimeanalysis.database.tupleset as tupleset
import analysis.lifetimeanalysis.database.mapping as mapping
import analysis.lifetimeanalysis.database.lattice as lattice


class TestSetIntersection(unittest.TestCase):
	def testMerge(self):
		a = set((1,2,5,6))
		b = set((1,3,5,7))

		c = lattice.setIntersectionSchema.merge(a, b)

		self.assertEqual(a, set((1,2,5,6)))
		self.assertEqual(b, set((1,3,5,7)))
		self.assertEqual(c, set((1,5)))

	def testInplaceMerge(self):
		a = set((1,2,5,6))
		b = set((1,3,5,7))

		c, changed = lattice.setIntersectionSchema.inplaceMerge(a, b)

		self.assertEqual(a, set((1,5)))
		self.assertEqual(b, set((1,3,5,7)))
		self.assertEqual(c, set((1,5)))
		self.assertEqual(changed, True)


	def testInplaceMergeNull(self):
		a = set((1,5))
		b = set((1,2,5,6))

		c, changed = lattice.setIntersectionSchema.inplaceMerge(a, b)

		self.assertEqual(a, set((1,5)))
		self.assertEqual(b, set((1,2,5,6)))
		self.assertEqual(c, set((1,5)))
		self.assertEqual(changed, False)

class TestSetUnion(unittest.TestCase):
	def testMerge(self):
		a = set((1,2,5,6))
		b = set((1,3,5,7))

		c = lattice.setUnionSchema.merge(a, b)

		self.assertEqual(a, set((1,2,5,6)))
		self.assertEqual(b, set((1,3,5,7)))
		self.assertEqual(c, set((1,2,3,5,6,7)))

	def testInplaceMerge(self):
		a = set((1,2,5,6))
		b = set((1,3,5,7))

		c, changed = lattice.setUnionSchema.inplaceMerge(a, b)

		self.assertEqual(a, set((1,2,3,5,6,7)))
		self.assertEqual(b, set((1,3,5,7)))
		self.assertEqual(c, set((1,2,3,5,6,7)))
		self.assertEqual(changed, True)

	def testInplaceMergeNull(self):
		a = set((1,2,5,6))
		b = set((1,5))

		c, changed = lattice.setUnionSchema.inplaceMerge(a, b)

		self.assertEqual(a, set((1,2,5,6)))
		self.assertEqual(b, set((1,5)))
		self.assertEqual(c, set((1,2,5,6)))
		self.assertEqual(changed, False)

class TestStructureSchema(unittest.TestCase):
	def testCreate(self):
		intSchema = structure.TypeSchema(int)
		s = structure.StructureSchema(('a', intSchema),
				       ('b', intSchema),
				       ('c', intSchema))

		self.assertEqual(s.field('b'), intSchema)
		self.assertRaises(structure.base.SchemaError, s.field, 'z')

	def testBadCreate(self):
		intSchema = structure.TypeSchema(int)
		self.assertRaises(structure.base.SchemaError, structure.StructureSchema, ('a', intSchema), ('b', intSchema), ('a', intSchema))

	def testValidate(self):
		intSchema = structure.TypeSchema(int)
		s = structure.StructureSchema(('a', intSchema), ('b', intSchema), ('c', intSchema))

		self.assert_(s.validateNoRaise((1, 2, 3)))
		self.assert_(not s.validateNoRaise((1, 2, 3.0)))
		self.assert_(not s.validateNoRaise((1, 2)))
		self.assert_(not s.validateNoRaise((1, 2, 3, 4)))


class TestStructure(unittest.TestCase):
	def setUp(self):
		intSchema = structure.TypeSchema(int)
		self.schema = structure.StructureSchema(
			('a', lattice.setUnionSchema),
			('b', lattice.setUnionSchema),
			)


	def testMerge(self):
		s1 = (set((2,)), None)
		s2 = (None, set((1,)))

		s3 = self.schema.merge(s1, s2)


		self.assertEqual(s1, (set((2,)), None))
		self.assertEqual(s2, (None, set((1,))))
		self.assertEqual(s3, (set((2,)), set((1,))))

	def testInplaceMerge1(self):
		s1 = (set((2,)), None)
		s2 = (None, set((1,)))
		s3 = (set((2,)), set((1,)))

		s4, changed = self.schema.inplaceMerge(s3, s1)

		self.assertEqual(s4, (set((2,)), set((1,))))
		self.assertEqual(changed, False)

		# s1 is NOT mutated.
		self.assertEqual(s1, (set((2,)), None))


	def testInplaceMerge2(self):
		s1 = (set((2,)), None)
		s2 = (None, set((1,)))
		s3 = (set((2,)), set((1,)))

		s4, changed = self.schema.inplaceMerge(s1, (set((3,)),None))

		self.assertEqual(s4, (set((2,3)), None))
		self.assertEqual(changed, True)

		# s1 is mutated.
		self.assertEqual(s1, (set((2,3)), None))


class TestTupleSet(unittest.TestCase):
	def setUp(self):
		intSchema = structure.TypeSchema(int)
		s = structure.StructureSchema(('a', intSchema), ('b', intSchema))
		schema = tupleset.TupleSetSchema(s)
		self.schema = schema


	def testInit(self):
		ts = self.schema.instance()
		ts.add(1, 2)
		ts.add(1, 3)
		ts.add(1, 2)

		self.assertEqual(len(ts), 2)
		for a, b in ts:
			self.assertEqual(a, 1)
			self.assert_(b == 2 or b == 3)

		ts.remove(1, 2)
		self.assertEqual(len(ts), 1)
		ts.remove(1, 3)
		self.assertEqual(len(ts), 0)

		self.assertRaises(structure.base.DatabaseError, ts.remove, 1, 2)





class TestMapping(unittest.TestCase):
	def setUp(self):
		intSchema = structure.TypeSchema(int)

		s = structure.StructureSchema(('a', intSchema), ('b', intSchema))
		v = lattice.setUnionSchema

		schema = mapping.MappingSchema(s, v)
		self.schema = schema


	def testAdd(self):
		m = self.schema.instance()

		m.merge((1, 2), (1,))
		m.merge((1, 2), (2,))
		m.merge((1, 3), (1,))

		self.assertEqual(len(m), 2)

		for key, data in m:
			if key == (1, 2):
				self.assertEqual(data, set((1, 2)))
			elif key == (1, 3):
				self.assertEqual(data, set((1,)))
			else:
				self.fail()


	def testForget(self):
		m = self.schema.instance()
		m.merge((1, 2), (1,))
		m.merge((1, 2), (2,))
		m.merge((1, 3), (1,3,))

		self.assertEqual(len(m), 2)

		f = m.forget()
		self.assertEqual(f, set((1, 2, 3)))


class TestMapMapForget(unittest.TestCase):
	def setUp(self):
		intSchema = structure.TypeSchema(int)

		schema = mapping.MappingSchema(intSchema, lattice.setUnionSchema)
		schema = mapping.MappingSchema(intSchema, schema)
		self.schema = schema

	def testForget(self):
		m = self.schema.instance()
		m[1].merge(2, (1,2,))
		m[1].merge(3, (1,3,))
		m[2].merge(2, (4,5,))


		f = m.forget().forget()
		self.assertEqual(f, set((1, 2, 3, 4, 5)))
