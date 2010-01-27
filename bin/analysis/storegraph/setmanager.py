import sys
from util.monkeypatch import xcollections

class CachedSetManager(object):
	def __init__(self):
		self.cache = xcollections.weakcache()
		self._emptyset = self.cache[frozenset()]

	def coerce(self, values):
		return self.cache[frozenset(values)]

	def empty(self):
		return self._emptyset

	def inplaceUnion(self, a, b):
		if a is b:
			return a
		elif not a:
			return self.cache[b]
		elif not b:
			return self.cache[a]
		else:
			return self.cache[a.union(b)]

	def diff(self, a, b):
		if a is b:
			return self._emptyset
		elif not b:
			return self.cache[a]
		else:
			return self.cache[a-b]

	def tempDiff(self, a, b):
		if a is b:
			return self._emptyset
		elif not b:
			return a
		else:
			return a-b

	def iter(self, s):
		return iter(s)

	def memory(self):
		mem = sys.getsizeof(self.cache)
		for s in self.cache:
			mem += sys.getsizeof(s)
		return mem
