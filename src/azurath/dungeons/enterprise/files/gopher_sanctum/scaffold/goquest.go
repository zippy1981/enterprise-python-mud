// Package main builds the _goquest CPython extension module.
//
//	go build -buildmode=c-shared -o ../questboard/_goquest<EXT_SUFFIX> .
package main

/*
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdlib.h>

// Defined in module.c. With //export in this file, the preamble may only declare.
PyObject* goquest_make_module(void);
int goquest_parse_bonus_args(PyObject* args, long long* base, const char** rank);
void goquest_raise_value_error(const char* msg);
*/
import "C"

import (
	"strings"
	"unsafe"
)

// goquest_bonus implements _goquest.bonus(base, rank). It runs with the GIL held.
//
//export goquest_bonus
func goquest_bonus(self *C.PyObject, args *C.PyObject) *C.PyObject {
	var base C.longlong
	var rank *C.char
	if C.goquest_parse_bonus_args(args, &base, &rank) == 0 {
		return nil // PyArg_ParseTuple already set a TypeError
	}

	var result C.longlong
	switch strings.ToUpper(C.GoString(rank)) {
	case "S":
		result = base * 3
	// TODO: A = x2, B = x1.5 (base * 3 / 2), C = x1
	default:
		// TODO: raise ValueError("unknown rank: ..."):
		//   build a C string with C.CString, free it with defer C.free(unsafe.Pointer(msg)),
		//   call C.goquest_raise_value_error(msg), and return nil
		_ = unsafe.Pointer(nil)
		return nil
	}
	return C.PyLong_FromLongLong(result) // new reference, owned by the caller
}

// PyInit__goquest is what `import _goquest` calls.
//
//export PyInit__goquest
func PyInit__goquest() *C.PyObject {
	return C.goquest_make_module()
}

func main() {}
