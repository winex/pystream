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

import util.canonical
import collections

__all__ = ['noMod', 'remapContextual', 'makeContextualAnnotation', 'annotationSet', 'mergeContextualAnnotation', 'ContextualAnnotation']

noMod = util.canonical.Sentinel('<no mod>')

ContextualAnnotation = collections.namedtuple('ContextualAnnotation', 'merged context')

def annotationSet(data):
	return tuple(sorted(data))

def makeContextualAnnotation(cdata):
	merged = set()
	for data in cdata: merged.update(data)
	merged = annotationSet(merged)

	cache = {} # Used to pool identical data
	return ContextualAnnotation(cache.setdefault(merged, merged), tuple([cache.setdefault(data, data) for data in cdata]))

def mergeAnnotationSet(a, b):
	s = set(a)
	s.update(b)
	return annotationSet(s)

def mergeContextualAnnotation(a, b):
	if a is None:
		return b
	elif b is None:
		return a
	else:
		return makeContextualAnnotation([mergeAnnotationSet(ca, cb) for ca, cb in zip(a.context, b.context)])

def remapContextual(cdata, remap, translator=None):
	if cdata is None: return None

	cout  = []

	for i in remap:
		if isinstance(i, (tuple, list)):
			if len(i) == 0:
				# No contexts
				cout.append(())
				continue
			elif len(i) > 1:
				# Merge multiple contexts
				data = set()
				for src in i:
					if src >= 0:
						if translator:
							data.update([translator(item) for item in cdata[1][src]])
						else:
							data.update(cdata[1][src])
				data = annotationSet(data)
				cout.append(data)
				continue
			else:
				# Single context
				i = i[0]
				# Fall through

		if i >= 0:
			data = cdata[1][i]
			if translator:
				data = annotationSet([translator(item) for item in data])
		else:
			data = ()

		cout.append(data)

	return makeContextualAnnotation(cout)

class Annotation(object):
	__slots__ = ()

	def rewrite(self, **kwds):
		# Assume only one level of inheritance. (__slots__ gets masked otherwise)
		slots = self.__slots__

		# Make sure extraneous keywords were not given.
		for name in kwds.iterkeys():
			assert name in slots, name

		# Fill in unspecified names with the old values
		for name in slots:
			if name not in kwds:
				kwds[name] = getattr(self, name)

		return type(self)(**kwds)

	def __repr__(self):
		parts = []
		slots = self.__slots__
		for name in slots:
			parts.append("%s=%r" % (name, getattr(self, name)))

		return "%s(%s)" % (type(self).__name__, ", ".join(parts))
