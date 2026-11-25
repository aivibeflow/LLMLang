package main

/*
#cgo LDFLAGS: -L${SRCDIR} -lchecked
#include "public.h"
*/
import "C"

import (
	"bufio"
	"fmt"
	"os"
)

func main() {
	input := bufio.NewReader(os.Stdin)
	output := bufio.NewWriter(os.Stdout)
	defer output.Flush()
	for {
		var word uint64
		var mode uint32
		if _, err := fmt.Fscan(input, &word, &mode); err != nil {
			return
		}
		slot := C.uint64_t(0xabad1234abcdef01)
		status := C.checked_add(C.uint64_t(word), C.uint32_t(mode), &slot)
		fmt.Fprintf(output, "%d %d\n", status, slot)
	}
}
