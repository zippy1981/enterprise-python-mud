/* C glue for the _goquest extension module.
 *
 * cgo can't call variadic C functions (PyArg_ParseTuple) or C macros, and a Go
 * file that uses //export may only *declare* C functions in its preamble. So the
 * method table, module definition and small shims live here, and cgo compiles
 * this file automatically because it sits in the same package directory.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "_cgo_export.h" /* declares goquest_bonus, implemented in Go */

static PyMethodDef goquest_methods[] = {
    {"bonus", (PyCFunction)goquest_bonus, METH_VARARGS,
     "bonus(base, rank, /) -> int\n\nMultiply base by the rank's bonus (S=3, A=2, B=1.5, C=1)."},
    {NULL, NULL, 0, NULL} /* sentinel */
};

static struct PyModuleDef goquest_module = {
    PyModuleDef_HEAD_INIT,
    "_goquest",                     /* m_name */
    "Quest maths, written in Go.",  /* m_doc */
    -1,                             /* m_size: no per-module state */
    goquest_methods,
};

PyObject* goquest_make_module(void) { return PyModule_Create(&goquest_module); }

int goquest_parse_bonus_args(PyObject* args, long long* base, const char** rank) {
    /* "L" = long long, "s" = UTF-8 str -> const char* (borrowed, valid while args lives) */
    return PyArg_ParseTuple(args, "Ls", base, rank);
}

void goquest_raise_value_error(const char* msg) { PyErr_SetString(PyExc_ValueError, msg); }
