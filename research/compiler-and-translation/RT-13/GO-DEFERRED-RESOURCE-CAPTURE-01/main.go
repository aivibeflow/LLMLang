package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
)

type handle struct {
	id   int
	file *os.File
}

type closeEvent struct {
	ID     int    `json:"id"`
	Status string `json:"status"`
}

type observation struct {
	Mode   string       `json:"mode"`
	Count  int          `json:"count"`
	Closes []closeEvent `json:"closes"`
	Live   []int        `json:"live_after_scope"`
}

func closeTracked(result *observation, value *handle) {
	status := "closed"
	if err := value.file.Close(); err != nil {
		if !errors.Is(err, os.ErrClosed) {
			panic(err)
		}
		status = "already-closed"
	}
	result.Closes = append(result.Closes, closeEvent{ID: value.id, Status: status})
}

func schedule(result *observation, handles []*handle) {
	switch result.Mode {
	case "declared-loop-capture":
		for _, current := range handles {
			defer func() { closeTracked(result, current) }()
		}
	case "assigned-loop-capture":
		var current *handle
		for _, current = range handles {
			defer func() { closeTracked(result, current) }()
		}
	case "snapshot-capture":
		for _, current := range handles {
			selected := current
			defer func() { closeTracked(result, selected) }()
		}
	case "direct-argument":
		for _, current := range handles {
			defer closeTracked(result, current)
		}
	default:
		panic("unknown capture profile")
	}
}

func run(mode string, count int) observation {
	result := observation{Mode: mode, Count: count, Closes: make([]closeEvent, 0), Live: make([]int, 0)}
	var handles []*handle
	for id := 1; id <= count; id++ {
		reader, writer, err := os.Pipe()
		if err != nil {
			panic(err)
		}
		if err := writer.Close(); err != nil {
			panic(err)
		}
		handles = append(handles, &handle{id: id, file: reader})
	}
	schedule(&result, handles)
	for _, value := range handles {
		if _, err := value.file.Stat(); err == nil {
			result.Live = append(result.Live, value.id)
			if err := value.file.Close(); err != nil {
				panic(err)
			}
		} else if !errors.Is(err, os.ErrClosed) {
			panic(err)
		}
	}
	return result
}

func main() {
	modes := []string{"declared-loop-capture", "assigned-loop-capture", "snapshot-capture", "direct-argument"}
	encoder := json.NewEncoder(os.Stdout)
	for _, mode := range modes {
		for count := 0; count <= 4; count++ {
			if err := encoder.Encode(run(mode, count)); err != nil {
				panic(fmt.Errorf("encode %s/%d: %w", mode, count, err))
			}
		}
	}
}
