// Admit one typed, closed Go function from the wrapping integer fixture.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"go/types"
	"os"
	"reflect"
	"strings"
)

const template = `package main

func admitted(a, b, enabled uint32, emit func(uint32), out *uint32) uint32 {
	emit(a)
	value := b
	if enabled != 0 {
		value = LEFT OP RIGHT
	}
	emit(value)
	*out = value
	return 0
}
`

type result struct {
	Status    string   `json:"status"`
	Operation string   `json:"operation,omitempty"`
	Operands  []string `json:"operands,omitempty"`
}

func shape(decl *ast.FuncDecl) string {
	decl.Name.Name = "admitted"
	var output bytes.Buffer
	filter := func(name string, value reflect.Value) bool {
		return name != "Obj" && name != "Doc" && value.Type() != reflect.TypeFor[token.Pos]()
	}
	if err := ast.Fprint(&output, nil, decl, filter); err != nil {
		panic(err)
	}
	return output.String()
}

func recognize(contents []byte) result {
	files := token.NewFileSet()
	f, err := parser.ParseFile(files, "candidate.go", contents, parser.SkipObjectResolution|parser.ParseComments)
	if err != nil {
		return result{Status: "parse-error"}
	}
	for _, group := range f.Comments {
		for _, comment := range group.List {
			if strings.HasPrefix(comment.Text, "//go:") ||
				strings.HasPrefix(comment.Text, "// +build") ||
				strings.HasPrefix(comment.Text, "//line ") ||
				strings.HasPrefix(comment.Text, "/*line ") {
				return result{Status: "unsupported-directive"}
			}
		}
	}
	if f.Name.Name != "main" || len(f.Decls) != 1 {
		return result{Status: "unsupported-inventory"}
	}
	decl, ok := f.Decls[0].(*ast.FuncDecl)
	if !ok {
		return result{Status: "unsupported-inventory"}
	}

	config := types.Config{}
	if _, err := config.Check("closedprobe", files, []*ast.File{f}, nil); err != nil {
		return result{Status: "type-error"}
	}
	actual := shape(decl)
	operations := []struct {
		name   string
		symbol string
	}{{"wrap_add", "+"}, {"wrap_sub", "-"}, {"wrap_mul", "*"}}
	for _, operation := range operations {
		for _, left := range []string{"a", "b"} {
			for _, right := range []string{"a", "b"} {
				render := strings.NewReplacer("LEFT", left, "RIGHT", right, "OP", operation.symbol)
				example, err := parser.ParseFile(token.NewFileSet(), "expected.go",
					render.Replace(template), parser.SkipObjectResolution)
				if err != nil {
					panic(err)
				}
				if shape(example.Decls[0].(*ast.FuncDecl)) == actual {
					return result{Status: "accepted", Operation: operation.name,
						Operands: []string{left, right}}
				}
			}
		}
	}
	return result{Status: "unsupported-shape"}
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: importer path.go")
		os.Exit(2)
	}
	source, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := json.NewEncoder(os.Stdout).Encode(recognize(source)); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
