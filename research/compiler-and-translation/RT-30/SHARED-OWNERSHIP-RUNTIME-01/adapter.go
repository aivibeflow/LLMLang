package main

/*
#cgo LDFLAGS: -L${SRCDIR} -lowned
#include "runtime.h"
*/
import "C"

//export step
func step(operation, actor, peer, handle, payload C.uint32_t) C.uint32_t {
	return C.rt_apply(operation, actor, peer, handle, payload)
}

func main() {}
