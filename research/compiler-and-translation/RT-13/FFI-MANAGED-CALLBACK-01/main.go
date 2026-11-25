package main

/*
#include "bridge.h"
*/
import "C"

import (
	"fmt"
	"os"
	"runtime"
	"runtime/cgo"
	"strconv"
	"syscall"
)

type context struct {
	offset    int
	owner     int
	contained bool
}

//export goCallback
func goCallback(self *C.session, ticket C.uint64_t, payload C.int, token C.uintptr_t) (result C.int) {
	var thread, ignored C.int
	if C.fixture_thread(self, ticket, &thread) != 0 ||
		C.fixture_retire(self, ticket) != 2 ||
		C.fixture_finish(self, ticket, &ignored) != 2 {
		return -88
	}
	if payload == 0 {
		runtime.GC()
	}
	held := cgo.Handle(token).Value().(*context)
	expected := C.int(2)
	if syscall.Gettid() == held.owner {
		expected = 1
	}
	if thread != expected {
		return -88
	}
	if held.contained {
		defer func() {
			if recovered := recover(); recovered != nil {
				result = -77
			}
		}()
	}
	if payload == -7 {
		panic("fixture callback failed")
	}
	return thread*1000 + payload*3 + C.int(held.offset)
}

func run(payload, profile, offset int) int {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	owner := syscall.Gettid()
	contained := os.Getenv("FIXTURE_UNCONTAINED") != "1"
	first := cgo.NewHandle(&context{offset: offset, owner: owner, contained: contained})
	second := cgo.NewHandle(&context{offset: offset + 7, owner: owner, contained: contained})
	defer first.Delete()
	defer second.Delete()
	flush := C.int(1)
	if os.Getenv("FIXTURE_UNFLUSHED") == "1" {
		flush = 0
	}
	return int(C.drive_go(C.uintptr_t(first), C.uintptr_t(second), C.int(payload), C.int(profile), flush))
}

func main() {
	if (len(os.Args)-1)%3 != 0 {
		os.Exit(2)
	}
	for i := 1; i < len(os.Args); i += 3 {
		var input [3]int
		for j := range input {
			value, err := strconv.Atoi(os.Args[i+j])
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(2)
			}
			input[j] = value
		}
		if status := run(input[0], input[1], input[2]); status != 0 {
			os.Exit(status)
		}
	}
}
