package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"
)

func run() error {
	input := bufio.NewReader(os.Stdin)
	output := bufio.NewWriter(os.Stdout)
	var request [16]byte
	var answer [20]byte
	for {
		if _, err := io.ReadFull(input, request[:]); err != nil {
			if err == io.EOF {
				return output.Flush()
			}
			return err
		}
		index := binary.LittleEndian.Uint32(request[:4])
		if index >= uint32(len(kernels)) {
			return fmt.Errorf("kernel index out of bounds: %d", index)
		}
		a := binary.LittleEndian.Uint32(request[4:8])
		b := binary.LittleEndian.Uint32(request[8:12])
		enabled := binary.LittleEndian.Uint32(request[12:])
		slot := uint32(0xabad1234)
		count := 0
		var events [2]uint32
		emit := func(value uint32) {
			events[count] = value
			count++
		}
		status := kernels[index](a, b, enabled, emit, &slot)
		binary.LittleEndian.PutUint32(answer[:4], status)
		binary.LittleEndian.PutUint32(answer[4:8], slot)
		binary.LittleEndian.PutUint32(answer[8:12], uint32(count))
		binary.LittleEndian.PutUint32(answer[12:16], events[0])
		binary.LittleEndian.PutUint32(answer[16:], events[1])
		if _, err := output.Write(answer[:]); err != nil {
			return err
		}
	}
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
