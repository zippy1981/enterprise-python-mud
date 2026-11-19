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
	// TODO: A = x2, B = x1.5 (base * 3 / 2), C = x1
	}
	return -1
}

// TODO: export GuildMotto(name *C.char) *C.char returning "For <name> and the Guild!"
//       (C.CString allocates with malloc, so the caller must free it)

// FreeString releases strings allocated by this library.
//
//export FreeString
func FreeString(p *C.char) {
	C.free(unsafe.Pointer(p))
}

func main() {}
