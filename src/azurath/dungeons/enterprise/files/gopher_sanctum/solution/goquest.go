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
	switch r := strings.ToUpper(C.GoString(rank)); r {
	case "S":
		result = base * 3
	case "A":
		result = base * 2
	case "B":
		result = base * 3 / 2
	case "C":
		result = base
	default:
		msg := C.CString("unknown rank: " + C.GoString(rank))
		defer C.free(unsafe.Pointer(msg))
		C.goquest_raise_value_error(msg)
		return nil // NULL + an error set = raise
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
