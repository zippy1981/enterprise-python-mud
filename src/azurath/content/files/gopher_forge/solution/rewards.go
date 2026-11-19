// Package main is built as a C shared library: go build -buildmode=c-shared
package main

/*
#include <stdlib.h>
*/
import "C"

import (
	"strings"
	"unsafe"
)

// CalculateBonus multiplies base by the rank's multiplier, or returns -1 for unknown ranks.
//
//export CalculateBonus
func CalculateBonus(base C.longlong, rank *C.char) C.longlong {
	switch strings.ToUpper(C.GoString(rank)) {
	case "S":
		return base * 3
	case "A":
		return base * 2
	case "B":
		return base * 3 / 2
	case "C":
		return base
	}
	return -1
}

// GuildMotto returns a newly malloc'd C string. Free it with FreeString.
//
//export GuildMotto
func GuildMotto(name *C.char) *C.char {
	return C.CString("For " + C.GoString(name) + " and the Guild!")
}

// FreeString releases strings allocated by this library.
//
//export FreeString
func FreeString(p *C.char) {
	C.free(unsafe.Pointer(p))
}

func main() {}
