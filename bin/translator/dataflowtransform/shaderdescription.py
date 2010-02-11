from .. import intrinsics
from language.python import ast
from language.glsl import ast as glsl

class IOInfo(object):
	def __init__(self):
		self.uniforms = set()
		self.inputs   = set()
		self.outputs  = set()

		self.builtin  = {}

		self.same     = {}

		self.fieldTrans = {}

		self.specialInputs  = {}
		self.specialOutputs = {}

class ProgramDescription(object):
	__slots__ = 'prgm', 'vscontext', 'fscontext', 'mapping', 'vs2fs', 'ioinfo'

	def __init__(self, prgm, vscontext, fscontext):
		self.prgm = prgm
		self.vscontext = vscontext
		self.fscontext = fscontext

		self.vs2fs = {}

	def makeMap(self, tree, slot, mapping):
		if tree.used:
			assert slot not in mapping
			mapping[slot] = tree.ioname

			assert tree.ioname not in self.vs2fs
			self.vs2fs[tree.ioname] = slot


	def handleOutputToLocal(self, tree, lcl, mapping):
		self.makeMap(tree, lcl, mapping)
		refs = lcl.annotation.references.merged
		self.traverse(tree, refs, mapping)

	def handleOutputToField(self, tree, field, mapping):
		self.makeMap(tree, field, mapping)
		refs = field
		self.traverse(tree, refs, mapping)

	def traverse(self, tree, refs, mapping):
		for fieldName, child in tree.fields.iteritems():
			for obj in refs:
				if fieldName in obj.slots:
					self.handleOutputToField(child, obj.slots[fieldName], mapping)

	def linkVarying(self):
		# Generate fs input => vs output mappings
		# This is a reverse mapping, as that makes subsequent operations easier

		vsoutputs = self.vscontext.shaderdesc.outputs.varying
		fsparams = self.fscontext.originalParams.params[2:]

		assert len(vsoutputs) == len(fsparams)

		mapping = {}

		for output, param in zip(vsoutputs, fsparams):
			self.handleOutputToLocal(output, param, mapping)

		self.mapping = mapping


	def link(self):
		# Uniform objects and fields have the same names, so it is unnecessary to link them.
		self.linkVarying()

	def markTraverse(self, refs, marks):
		for ref in refs:
			for field in ref:
				self.markField(field, marks)

	def markEquivilents(self, field, marks):
		lcls = []

		for fields in (self.vscontext.shaderdesc.fields, self.fscontext.shaderdesc.fields):
			if field in fields:
				lcl = fields[field]
				marks.add(lcl)
				lcls.append(lcl)

		if len(lcls) > 0:
			self.ioinfo.fieldTrans[field] = lcls[0]

		if len(lcls) > 1:
			self.ioinfo.same[lcls[0]] = lcls[1]
			self.ioinfo.same[lcls[1]] = lcls[0]

	def markField(self, field, marks):
		if field not in marks and not intrinsics.isIntrinsicSlot(field):
			marks.add(field)
			self.markEquivilents(field, marks)

			self.markTraverse(field, marks)

	def markParam(self, param, marks):
		if param.isDoNotCare(): return
		marks.add(param)
		self.markTraverse(param.annotation.references.merged, marks)


	def markParams(self, context):
		params = context.originalParams
		self.markParam(params.params[0], self.ioinfo.uniforms)

		# TODO what about the context?
		context.shaderdesc.outputs.markSpecial(self.ioinfo)

		for param in params.params[2:]:
			self.markParam(param, self.ioinfo.inputs)

	def makeIOInfo(self):
		self.ioinfo = IOInfo()

		self.markParams(self.vscontext)
		self.markParams(self.fscontext)

		self.vscontext.shaderdesc.outputs.updateInfo(self.ioinfo)
		self.fscontext.shaderdesc.outputs.updateInfo(self.ioinfo)


		fsfields = self.fscontext.shaderdesc.fields
		for src, dst in self.vs2fs.iteritems():
			dst = fsfields.get(dst, dst)
			self.ioinfo.same[src] = dst

		return self.ioinfo

class ShaderDescription(object):
	__slots__ = 'fields', 'outputs'

class OutputBase(object):
	__slots__ = ()

	def updateInfo(self, info):
		info.outputs.update(self.collectIONames())
		self.getBuiltin(info)

	def generateOutput(self, tree, outputs):
		if tree.used:
			if tree.ioname is None:
				tree.ioname = ast.IOName(None)
			outputs.append(ast.Output(tree._lcl, tree.ioname))

		for child in tree.fields.itervalues():
			self.generateOutput(child, outputs)

	def generateOutputStatements(self):
		outputs = []

		for tree in self.getOutputs():
			self.generateOutput(tree, outputs)

		return ast.OutputBlock(outputs)

	def _collectIONames(self, tree, outputs):
		if tree.used and tree.ioname is not None:
			outputs.append(tree.ioname)

		for child in tree.fields.itervalues():
			self._collectIONames(child, outputs)

	def collectIONames(self):
		outputs = []

		for tree in self.getOutputs():
			self._collectIONames(tree, outputs)

		return outputs

class VSOutputDescription(OutputBase):
	__slots__ = 'position', 'varying'

	def collectUsed(self):
		used = set()
		self.position.collectUsed(used)

		for var in self.varying:
			var.collectUsed(used)

		return used

	def getBuiltin(self, info):
		vec4T = intrinsics.intrinsicTypeNodes[intrinsics.vec.vec4]
		info.builtin[self.position.ioname] = glsl.OutputDecl(None, False, False, True, vec4T, 'gl_Position')

	def getOutputs(self):
		outputs = [self.position]
		outputs.extend(self.varying)
		return outputs

	def markSpecial(self, ioinfo):
		ioinfo.specialOutputs[self.position.ioname] = 'gl_Position'


class FSOutputDescription(OutputBase):
	__slots__ = 'colors', 'depth'

	def collectUsed(self):
		used = set()
		if self.depth:
			self.depth.collectUsed(used)

		for color in self.colors:
			color.collectUsed(used)

		return used

	def getBuiltin(self, info):
		if self.depth:
			floatT = intrinsics.intrinsicTypeNodes[float]
			info.builtin[self.position.ioname] = glsl.OutputDecl(None, False, False, True, floatT, 'gl_Depth')

	def getOutputs(self):
		outputs = []
		if self.depth:
			outputs.append(self.depth)
		outputs.extend(self.colors)
		return outputs

	def markSpecial(self, ioinfo):
		if self.depth:
			ioinfo.specialOutputs[self.depth.ioname] = 'gl_Depth'



class TreeNode(object):
	def __init__(self, lcl):
		self._lcl = lcl
		self.fields = {}
		self.used   = intrinsics.isIntrinsicType(self.pythonType())
		self.ioname = None

	def refs(self):
		return self._lcl.annotation.references.merged

	def pythonType(self):
		refs = self.refs()
		pt = refs[0].xtype.obj.pythonType()
		for ref in refs[1:]:
			assert pt is ref.xtype.obj.pythonType()
		return pt

	def field(self, fieldName, lcl):
		tree = TreeNode(lcl)
		self.fields[fieldName] = tree
		return tree

	def extractTuple(self):
		array = {}
		length = None

		refs = self.refs()
		for ref in refs:
			assert ref.xtype.obj.pythonType() is tuple, refs

		for fieldName, child in self.fields.iteritems():
			if fieldName.type == 'LowLevel':
				if fieldName.name.pyobj == 'length':
					length = child.refs()[0].xtype.obj.pyobj

			elif fieldName.type == 'Array':
				array[fieldName.name.pyobj] = child
			else:
				assert False, fieldName

		assert len(array) == length

		return tuple([array[i] for i in range(length)])
