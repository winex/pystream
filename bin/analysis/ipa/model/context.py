from . import invocation, region, objectname
from .. constraints import flow, calls, qualifiers, node

class Context(object):
	def __init__(self, analysis, signature):
		self.analysis    = analysis
		self.signature   = signature

		self.params = []
		self.returns = []
		self.vparamField = []

		self.region = region.Region(self)
		self.locals = {}
		self.fields = {}

		self.constraints = []

		self.calls       = []
		self.dcalls      = []
		self.fcalls      = []

		self.dirtycalls       = []
		self.dirtydcalls      = []
		self.dirtyfcalls      = []

		self.invokeIn  = {}
		self.invokeOut = {}

		self.external = False

		self.dirtyflags   = []
		self.dirtyobjects = []

		self.dirtycriticals = []
		self.criticalOps = []

	def dirtyFlags(self, node):
		self.dirtyflags.append(node)

	def processFlags(self, callback):
		while self.dirtyflags:
			node = self.dirtyflags.pop()
			node.dirty = False
			callback(self, node)

	def dirtyObject(self, node):
		self.dirtyobjects.append(node)

	def processObjects(self, callback):
		while self.dirtyobjects:
			node = self.dirtyobjects.pop()
			node.dirty = False
			callback(self, node)

	def dirtyCritical(self, node, critical):
		assert critical._dirty
		assert node.context is self
		assert node not in self.dirtycriticals
		self.dirtycriticals.append(node)

	def criticalOp(self, constraint):
		self.criticalOps.append(constraint)

	def existingPyObj(self, pyobj, qualifier=qualifiers.HZ):
		obj = self.analysis.pyObj(pyobj)
		xtype = self.analysis.canonical.existingType(obj)
		return self.analysis.objectName(xtype, qualifier)

	def allocatePyObj(self, pyobj):
		ao  = self.existingPyObj(pyobj, qualifiers.HZ)

		# TODO do we need to set the type pointer?
		tao = self.existingPyObj(type(pyobj), qualifiers.HZ) # Yes, it is not global
		self.setTypePointer(ao, tao)

		return ao

	def setTypePointer(self, obj, typeObj):
		assert obj.isObjectName(), obj
		assert typeObj.isObjectName(), typeObj

		typeptr = self.field(obj, 'LowLevel', self.analysis.pyObj('type'))
		typeptr.clearNull()
		typeptr.updateSingleValue(typeObj)

	def allocate(self, typeObj, node):
		assert typeObj.isObjectName(), typeObj

		inst  = self.analysis.pyObjInst(typeObj.pyObj())
		xtype = self.analysis.canonical.pathType(None, inst, node)
		obj   = self.analysis.objectName(xtype, qualifiers.HZ)

		self.setTypePointer(obj, typeObj)

		return obj

	def getInvoke(self, op, dst):
		key = op, dst
		inv = self.invokeOut.get(key)
		if inv is None:
			inv = invocation.Invocation(self, op, dst)
		return inv


	def dirtySlot(self, slot):
		self.analysis.dirtySlot(slot)

	def dirtyCall(self, call):
		self.dirtycalls.append(call)

	def dirtyDCall(self, call):
		self.dirtydcalls.append(call)

	def dirtyFCall(self, call):
		self.dirtyfcalls.append(call)

	def constraint(self, constraint):
		self.constraints.append(constraint)
		constraint.init(self)

	def call(self, op, selfarg, args, kwds, varg, karg, targets):
		call = calls.CallConstraint(self, op, selfarg, args, kwds, varg, karg, targets)
		self.calls.append(call)

	def dcall(self, op, code, selfarg, args, kwds, varg, karg, targets):
		if varg is None:
			return self.fcall(op, code, selfarg, args, kwds, [], karg, targets)
		else:
			call = calls.DirectCallConstraint(self, op, code, selfarg, args, kwds, varg, karg, targets)
			self.dcalls.append(call)
			return call

	def fcall(self, op, code, selfarg, args, kwds, varg, karg, targets):
		call = calls.FlatCallConstraint(self, op, code, selfarg, args, kwds, varg, karg, targets)
		self.fcalls.append(call)
		return call


	def local(self, lcl):
		if lcl not in self.locals:
			slot = node.ConstraintNode(self, lcl)
			self.locals[lcl] = slot
		else:
			slot = self.locals[lcl]
		return slot

	def field(self, obj, fieldType, name):
		return self.region.object(obj).field(fieldType, name)

	def assign(self, src, dst):
		constraint = flow.CopyConstraint(src, dst)
		self.constraint(constraint)

	def load(self, obj, fieldtype, field, dst):
		constraint = flow.LoadConstraint(obj, fieldtype, field, dst)
		self.constraint(constraint)

	def check(self, obj, fieldtype, field, dst):
		constraint = flow.CheckConstraint(obj, fieldtype, field, dst)
		self.constraint(constraint)

	def store(self, src, obj, fieldtype, field):
		constraint = flow.StoreConstraint(src, obj, fieldtype, field)
		self.constraint(constraint)

	def updateCallgraph(self):
		changed = False

		for queue in (self.dirtycalls, self.dirtydcalls, self.dirtyfcalls):
			while queue:
				call = queue.pop()
				call.resolve(self)
				changed = True

		return changed
