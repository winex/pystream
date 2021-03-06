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

# Unions heap objects into memory regions
# Basically, if two different objects can ever be refered to with
# the same pointer, they are collapsed into the same region.
# Note: regions may have cyclic points-to relationchips.
# As such, this analysis is not sound for "region allocation."

# Also, if a reference is "optionally None" there will be problems.
# In general, imutable objects should not be fused?

import PADS.UnionFind

import collections

from analysis.astcollector import getOps

from language.python import ast

class Region(object):
	def __init__(self, objects):
		self.objects = frozenset(objects)

	def __contains__(self, obj):
		return obj in self.objects

class RegionAnalysis(object):
	def __init__(self, extractor, entryPoints, liveCode):
		self.extractor = extractor
		self.entryPoints = entryPoints
		self.liveCode = liveCode
		self.uf = PADS.UnionFind.UnionFind()

		self.liveObjs = {}
		self.liveFields = {}

	def merge(self, references):
		if references:
			self.uf.union(*references)

	def process(self):
		# TODO get all fields from heap?

		# Local references
		for code in self.liveCode:
			self.liveObjs[code]   = set()
			self.liveFields[code] = set()

			ops, lcls = getOps(code)
			for op in ops:

				self.liveFields[code].update(op.annotation.reads[0])
				self.liveFields[code].update(op.annotation.modifies[0])

				if not op.annotation.invokes[0]:
					# If the op does not invoke, it does real work.
					self.merge(op.annotation.reads[0])
					self.merge(op.annotation.modifies[0])

					# TODO seperate by concrete field type before merge

				for cobj in op.annotation.allocates[0]:
					if not cobj.leaks:
						self.liveObjs[code].add(cobj)

			for lcl in lcls:
				for ref in lcl.annotation.references[0]:
					if not ref.leaks:
						self.liveObjs[code].add(ref)

			#print code, len(self.liveFields[code])


	def printGroups(self):

		lut = collections.defaultdict(set)

		for slot in self.uf:
			lut[self.uf[slot]].add(slot)


		print
		print "Groups"
		for key, values in lut.iteritems():
			print key
			for slot in values:
				if slot is not key:
					print '\t', slot
			print

def evaluate(extractor, entryPoints, liveCode):
	ra = RegionAnalysis(extractor, entryPoints, liveCode)
	ra.process()
	return ra
