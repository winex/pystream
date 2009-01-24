from __future__ import absolute_import

import sys
import copy
from opcode import opmap
from dis import dis

import inspect

from . disassembler import disassemble

# HACK
import programIR.python.ast as cfg

#from common.ssa import DeadCodeEliminator

import decompiler.errors

from util import moduleForGlobalDict

from decompiler.flowblocks import *

import collections

from decompiler.destacker import destack
from . structuralanalyzer import StructuralAnalyzer
from . import ssitransform

from decompiler.flowblockdump import FlowBlockDump
from common.simplecodegen import SimpleCodeGen


import analysis.analysisdatabase
import optimization.simplify

def decompile(func, extractor, trace=False, ssa=True):
	assert not isinstance(extractor, bool)

	# HACK can't find modules for "fake" globals.
	try:
		mname, module = moduleForGlobalDict(func.func_globals)
	except:
		mname = 'unknown_module'

	return decompileCode(extractor, func.func_code, mname, trace=trace, ssa=ssa)

def decompileCode(extractor, code, mname, trace=False, ssa=True):
	return Decompiler(extractor).disassemble(code, mname, trace=trace, ssa=ssa)

def getargs(co):
    nargs = co.co_argcount
    args = list(co.co_varnames[:nargs])

    vargs, kargs = None, None

    if co.co_flags & inspect.CO_VARARGS:
        vargs = co.co_varnames[nargs]
        nargs += 1

    if co.co_flags & inspect.CO_VARKEYWORDS:
        kargs = co.co_varnames[nargs]

    return args, vargs, kargs

class Decompiler(object):
	def __init__(self, extractor):
		self.extractor = extractor

	def disassemble(self, code, mname, trace=False, ssa=True):
		argnames, vargs, kargs = getargs(code)

		inst, targets = disassemble(code)

		name = code.co_name.replace('<','').replace('>','')

		if trace:
			print "CODE", name
			print code.co_argcount
			print code.co_varnames
			self.dump(inst,targets)

		root = BlockBuilder().process(inst)

		pre = True
		post = True

		if trace and pre:
			FlowBlockDump().process(name+"_pre", root)


		try:
			StructuralAnalyzer().process(root.entry(), trace)
		finally:
			if trace and post:
				FlowBlockDump().process(name+"_post", root)

		root = destack(mname, name, root, argnames, vargs, kargs, self.extractor, decompileCode, trace)

		if ssa:
			root = ssitransform.ssiTransform(root)

		# Flow sensitive, works without a ssa or ssi transform.
		optimization.simplify.simplify(self.extractor, analysis.analysisdatabase.DummyAnalysisDatabase(), root.code)


		if trace:
			SimpleCodeGen(sys.stdout).walk(root)

		return root


	def dump(self, inst, targets):

		loopstack = []
		looplevel = 0

		print
		for i in range(len(inst)):
			instruction = inst[i]

			if loopstack and loopstack[-1] == i:
				loopstack.pop()
				looplevel -= 1

			if instruction.opcode == opmap['SETUP_LOOP']:
				looplevel += 1
				loopstack.append(instruction.arg)

			jin  = ">>" if i in targets else "  "
			jout = "<<" if instruction.isFlowControl() else "  "
			indent = '\t'*looplevel
			arg = str(instruction.arg) if instruction.hasArgument() else ""
			print "%4d %s%s%s %-15s %s" % (i, jin, jout, indent, instruction.neumonic(), arg)
		print

class BlockBuilder(object):
	def makeLink(self, a, b, region):
		self.instOut[a].append(b)
		self.instIn[b].append(a)

		if not self.instOut[b]:
			self.queue.append((b, region))

	def linkInstruction(self, i, inst, region):
		op = inst.opcode

		if op == opmap['JUMP_IF_FALSE']:
			block = Switch(region)
			self.makeLink(i, i+1, region)
			self.makeLink(i, inst.arg, region)
		elif op == opmap['JUMP_IF_TRUE']:
			block = Switch(region)
			self.makeLink(i, inst.arg, region)
			self.makeLink(i, i+1, region)
		elif op == opmap['RETURN_VALUE']:
			block = Return(region)
		elif op == opmap['BREAK_LOOP']:
			block = Break(region)
		elif op == opmap['JUMP_FORWARD'] or op == opmap['JUMP_ABSOLUTE']:
			block = None # Eliminate this block.
			self.makeLink(i, inst.arg, region)
		elif op == opmap['FOR_ITER']:
			block = ForIter(region)
			self.makeLink(i, i+1, region)
			self.makeLink(i, inst.arg, region)
		elif op == opmap['SETUP_LOOP']:
			block = LoopRegion(region)
			self.makeLink(i, i+1, block)
			self.makeLink(i, inst.arg, region)
			#region = block
		elif op == opmap['SETUP_FINALLY']:
			block = FinallyRegion(region)
			self.makeLink(i, i+1, block)
			self.makeLink(i, inst.arg, region)
			#region = block
		elif op == opmap['SETUP_EXCEPT']:
			block = ExceptRegion(region)
			self.makeLink(i, i+1, block)
			self.makeLink(i, inst.arg, region)
			#region = block
		elif op == opmap['RAISE_VARARGS']:
			block = Raise(region, inst.arg)
		elif op == opmap['POP_BLOCK']:
			assert not inst.isFlowControl()
			#block = None
			block = Linear(region)
			block.instructions.append(inst)
			self.makeLink(i, i+1, region.region)

			assert not region in self.regionExit
			self.regionExit[region] = (i, i+1)

		elif op == opmap['END_FINALLY']:
			block = EndFinally(region)
			self.makeLink(i, i+1, region)
		else:
			assert not inst.isFlowControl()
			block = Linear(region)
			block.instructions.append(inst)
			self.makeLink(i, i+1, region)

		self.blocks[i] = block

	def reachBlock(self, i):
		if i in self.merges:
			return self.merges[i]

		# Skip unconditional jumps
		block = self.blocks[i]
		while not block:
			assert False # Depricated.

			o = self.instOut[i]
			assert len(o) == 1
			i = o[0]
			block = self.blocks[i]


		if i in self.merges:
			return self.merges[i]

		return block

	def linkBlock(self, i, block):
		assert block.region

		if block.isRegion():
			assert len(self.instOut[i]) == 2
			head = self.reachBlock(self.instOut[i][0])
			exceptional = self.reachBlock(self.instOut[i][1])

			if block in self.regionExit:
				exitEdge = self.regionExit[block]
				normal = self.reachBlock(exitEdge[1])
			else:
				# No normal exiting edges?
				normal = None

			block.setHead(head)
			outs = (normal, exceptional)

		else:
			outs = []
			for o in self.instOut[i]:
				o = self.reachBlock(o)
				assert o.region, o

				if block.region != o.region:
					if block.region.region == o.region:
						# An edge exiting a region.
						assert not block.isRegion()
						o = block.region.exit()
						assert block.region == o.region
					else:
						assert False

				outs.append(o)

		for o in outs:
			assert not o or block.region == o.region, (block, o)

		block.setNext(*outs)

	def process(self, instructions):
		self.instIn 	= collections.defaultdict(list)
		self.instOut 	= collections.defaultdict(list)
		self.blocks 	= {}
		self.merges	= {}
		self.regionExit = {}

		func = Function(None)

		self.queue = [(0, func)]

		while self.queue:
			i, region = self.queue.pop()
			inst = instructions[i]

			if not self.instOut[i]:
				self.linkInstruction(i, inst, region)


		self.eliminateNullBlocks()

		# Create merges
		for i, o in self.instIn.iteritems():
			if not i in self.rename and len(o) > 1:
				next = self.reachBlock(i)

				merge = Merge(next.region)
				merge.setNext(next)

				self.merges[i] = merge

		# Connect the blocks
		func.setHead(self.blocks[0])
		for i, block in self.blocks.iteritems():
			if block:
				self.linkBlock(i, block)

		# Fuse adjacent linear blocks
		self.fuseLinear(func)

		return func

	def eliminateNullBlocks(self):
		# Rename to eliminate the null blocks
		self.rename = {}
		for i, block in self.blocks.iteritems():
			if not block:
				assert len(self.instOut[i]) == 1
				self.rename[i] = self.instOut[i][0]

		# Reach the renames through any chains that exist.
		for a, b in self.rename.iteritems():
			while b in self.rename:
				b = self.rename[b]
			self.rename[a] = b

		# Apply the renames.
		newIn 	= collections.defaultdict(list)
		newOut 	= collections.defaultdict(list)

		for i, outs in self.instOut.iteritems():
			for o in outs:
				o = self.rename.get(o, o)
				newOut[i].append(o)
				newIn[o].append(i)

		self.instOut = newOut
		self.instIn = newIn

		# Rename the exits.
		newExit = {}
		for r, (a, b) in self.regionExit.iteritems():
			#r = self.rename.get(r, r)
			a = self.rename.get(a, a)
			b = self.rename.get(b, b)

			assert not r in newExit
			assert a != b
			newExit[r] = (a, b)
		self.regionExit = newExit

	def fuseLinear(self, root):
		queue = []
		processed = set()

		def enqueue(block):
			if not block in processed:
				queue.append(block)
				processed.add(block)
		enqueue(root)

		while queue:
			block = queue.pop()
			assert block.region == root.region

			if isinstance(block, Linear):
				# If the current block is linear
				# and the next block can be fused,
				# fuse.
				while isinstance(block.next, Linear):
					assert block.region == block.next.region
					assert block.next.prev == block

					block.instructions.extend(block.next.instructions)
					block.next.next.replacePrev(block.next, block)
					block.next = block.next.next
			elif block.isRegion():
				assert block.entry().region == block
				self.fuseLinear(block.entry())

			# Explore the decendants.
			for next in block.getNext():
				assert not next or next.region == block.region, (block, block.region, next, next.region)
				enqueue(next)
