// _pystream.cpp : Defines the entry point for the DLL application.
//

#include "stdafx.h"

// HACK as this is private...
typedef struct {
	PyObject_HEAD
		PyWrapperDescrObject *descr;
	PyObject *self;
} wrapperobject;

PyObject *
int_from_ptr(void *ptr)
{
	return PyInt_FromSsize_t(Py_ssize_t(ptr));
}

PyObject *
tup_from_ptrs(void *ptr0, void *ptr1)
{
		PyObject *tup = PyTuple_New(2);
		PyTuple_SET_ITEM(tup, 0, int_from_ptr(ptr0));
		PyTuple_SET_ITEM(tup, 1, int_from_ptr(ptr1));
		return tup;
}

PyObject *
PyCFunction_cfuncptr(PyObject *self, PyObject *args)
{
	PyObject *func;
	void *ptr = 0;

	if (!PyArg_ParseTuple(args, "O:cfuncptr", &func)) return NULL;

	if (PyCFunction_Check(func)) 
	{
		ptr = PyCFunction_GetFunction(func);
	}
	else if (PyObject_TypeCheck(func, &PyWrapperDescr_Type))
	{
		ptr = ((PyWrapperDescrObject *)func)->d_wrapped;
		void *ptr_wrap = ((PyWrapperDescrObject *)func)->d_base->wrapper;

		// The pointers interact.
		return tup_from_ptrs(ptr, ptr_wrap);
	}
	// 2.5+?
	else if (strcmp(func->ob_type->tp_name, "method_descriptor") == 0) // Horrible hack, but there seems to be no alternative.
	{
		ptr = ((PyMethodDescrObject *)func)->d_method->ml_meth;
	}
	// 2.6
	else if (strcmp(func->ob_type->tp_name, "method-wrapper") == 0) // Horrible hack, but there seems to be no alternative.
	{
		ptr = ((wrapperobject *)func)->descr->d_base->wrapper;
	}
	else
	{
		PyErr_SetString(PyExc_TypeError, "Argument must wrap a c function pointer.");
		return NULL;
	}

	return int_from_ptr(ptr); 
}

PyObject *
PyCFunction_getsetptrs(PyObject *self, PyObject *args)
{
	PyObject *func;
	PyObject *tup;
	void *get = 0;
	void *set = 0;

	if (!PyArg_ParseTuple(args, "O:getsetptrs", &func)) return NULL;

	if (strcmp(func->ob_type->tp_name, "getset_descriptor") == 0)
	{
		get = ((PyGetSetDescrObject *)func)->d_getset->get;
		set = ((PyGetSetDescrObject *)func)->d_getset->set;
	}
	else
	{
		PyErr_SetString(PyExc_TypeError, "Argument must be a getset.");
		return NULL;
	}

	return tup_from_ptrs(get, set);
}

static PyMethodDef BindMethods[] = {
	{"cfuncptr",  PyCFunction_cfuncptr,   METH_VARARGS, ""},
	{"getsetptrs", PyCFunction_getsetptrs, METH_VARARGS, ""},
	{NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC init_pystream()
{
	Py_InitModule3("_pystream", BindMethods, "");
}


