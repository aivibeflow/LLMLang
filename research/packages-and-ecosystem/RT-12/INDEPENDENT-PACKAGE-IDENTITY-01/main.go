package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"os"
	"path"
	"regexp"
	"slices"
	"strings"

	"github.com/BurntSushi/toml"
)

type request struct {
	Mode     string         `json:"mode"`
	Value    any            `json:"value"`
	BytesHex string         `json:"bytes_hex"`
	Manifest string         `json:"manifest"`
	Index    map[string]any `json:"index"`
}

type response struct {
	Admitted  bool   `json:"admitted"`
	Canonical string `json:"canonical_hex,omitempty"`
	Index     string `json:"index_hash,omitempty"`
	Root      string `json:"package_root,omitempty"`
}

func atom(out *bytes.Buffer, tag byte, data []byte) {
	out.WriteByte(tag)
	length(out, len(data))
	out.Write(data)
}

func length(out *bytes.Buffer, count int) {
	if uint64(count) > uint64(^uint32(0)) {
		panic("value outside finite fixture")
	}
	out.Write(binary.BigEndian.AppendUint32(nil, uint32(count)))
}

func appendValue(out *bytes.Buffer, value any) error {
	switch typed := value.(type) {
	case nil:
		out.WriteByte('N')
	case bool:
		if typed {
			out.WriteByte('T')
		} else {
			out.WriteByte('F')
		}
	case string:
		atom(out, 'S', []byte(typed))
	case []byte:
		atom(out, 'B', typed)
	case int64:
		atom(out, 'I', []byte(fmt.Sprint(typed)))
	case json.Number:
		number, ok := new(big.Int).SetString(string(typed), 10)
		if !ok {
			return errors.New("only integer JSON numbers are admitted")
		}
		atom(out, 'I', []byte(number.String()))
	case []any:
		out.WriteByte('L')
		length(out, len(typed))
		for _, item := range typed {
			if err := appendValue(out, item); err != nil {
				return err
			}
		}
	case map[string]any:
		keys := make([]string, 0, len(typed))
		for key := range typed {
			keys = append(keys, key)
		}
		// The canonical text encoding sorts length before code units.
		slices.SortFunc(keys, func(left, right string) int {
			if len(left) != len(right) {
				return len(left) - len(right)
			}
			return strings.Compare(left, right)
		})
		out.WriteByte('M')
		length(out, len(keys))
		for _, key := range keys {
			atom(out, 'S', []byte(key))
			if err := appendValue(out, typed[key]); err != nil {
				return err
			}
		}
	default:
		return fmt.Errorf("unsupported canonical value %T", value)
	}
	return nil
}

func encode(value any) ([]byte, error) {
	var buffer bytes.Buffer
	err := appendValue(&buffer, value)
	return buffer.Bytes(), err
}

func digest(domain string, value any) (string, error) {
	var buffer bytes.Buffer
	buffer.WriteString("LLMLANG\x00" + domain + "\x00")
	if err := appendValue(&buffer, value); err != nil {
		return "", err
	}
	return fmt.Sprintf("sha256:%x", sha256.Sum256(buffer.Bytes())), nil
}

var hash = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
var tables = map[string][]string{
	"package": {"id", "name", "version", "description"},
	"content": {"roots", "dependency_policy", "content_root", "resolution_inputs"},
	"index":   {"path", "format_version", "logical_hash"},
	"cache":   {"indexes"},
}

func isHash(value any) bool {
	text, ok := value.(string)
	return ok && hash.MatchString(text)
}

func relative(value any) bool {
	text, ok := value.(string)
	if !ok || text == "." || path.IsAbs(text) || path.Clean(text) != text || strings.Contains(text, "\\") {
		return false
	}
	return !slices.Contains(strings.Split(text, "/"), "..")
}

func strictOne(value any) bool {
	version, ok := value.(int64)
	return ok && version == 1
}

func parseManifest(text string) (map[string]any, error) {
	var decoded map[string]any
	if _, err := toml.Decode(text, &decoded); err != nil {
		return nil, err
	}
	if decoded["format"] != "llmlang.package" || !strictOne(decoded["schema_version"]) {
		return nil, errors.New("bad manifest version")
	}
	for key, entry := range decoded {
		if key == "format" || key == "schema_version" {
			continue
		}
		allowed, known := tables[key]
		fields, isTable := entry.(map[string]any)
		if !known || !isTable {
			return nil, errors.New("unexpected manifest table")
		}
		for name := range fields {
			if !slices.Contains(allowed, name) {
				return nil, errors.New("unexpected manifest field")
			}
		}
	}

	content, contentOK := decoded["content"].(map[string]any)
	index, indexOK := decoded["index"].(map[string]any)
	if !contentOK || !indexOK || !strictOne(index["format_version"]) ||
		!isHash(index["logical_hash"]) || !relative(index["path"]) || !isHash(content["content_root"]) {
		return nil, errors.New("bad content or index fields")
	}
	roots, ok := content["roots"].([]any)
	if !ok || len(roots) == 0 {
		return nil, errors.New("empty or invalid root array")
	}
	seen := make(map[string]bool)
	for _, root := range roots {
		if !isHash(root) || seen[root.(string)] {
			return nil, errors.New("unknown or repeated root")
		}
		seen[root.(string)] = true
	}
	switch content["dependency_policy"] {
	case "closure", "roots_only", "closure_with_optional":
	default:
		return nil, errors.New("invalid dependency policy")
	}
	if value, exists := content["resolution_inputs"]; exists {
		if _, valid := value.(map[string]any); !valid {
			return nil, errors.New("invalid resolution inputs")
		}
	}
	if cache, present := decoded["cache"].(map[string]any); present {
		if inspect, supplied := cache["indexes"]; supplied {
			names, ok := inspect.([]any)
			if !ok {
				return nil, errors.New("cache indexes must be paths")
			}
			visited := make(map[string]bool)
			for _, name := range names {
				if !relative(name) || name == index["path"] || visited[name.(string)] {
					return nil, errors.New("bad cache index path")
				}
				visited[name.(string)] = true
			}
		}
	}
	return decoded, nil
}

func orderedIndex(index map[string]any) (map[string]any, error) {
	expected := []string{"objects", "dependencies", "exports", "modules"}
	if len(index) != len(expected) {
		return nil, errors.New("unexpected logical tables")
	}
	ordered := make(map[string]any)
	for _, name := range expected {
		rows, ok := index[name].([]any)
		if !ok {
			return nil, errors.New("invalid index table")
		}
		keyed := make(map[string]any)
		keys := make([]string, 0, len(rows))
		for _, row := range rows {
			binaryKey, err := encode(row)
			if err != nil {
				return nil, err
			}
			key := string(binaryKey)
			if _, duplicate := keyed[key]; duplicate {
				return nil, errors.New("duplicate logical row")
			}
			keyed[key] = row
			keys = append(keys, key)
		}
		slices.Sort(keys)
		output := make([]any, 0, len(keys))
		for _, key := range keys {
			output = append(output, keyed[key])
		}
		ordered[name] = output
	}
	return ordered, nil
}

func verifyPackage(query request) (response, error) {
	document, err := parseManifest(query.Manifest)
	if err != nil {
		return response{}, err
	}
	normalized, err := orderedIndex(query.Index)
	if err != nil {
		return response{}, err
	}
	included := make(map[string]bool)
	for _, row := range normalized["objects"].([]any) {
		if record, ok := row.(map[string]any); ok {
			if h, valid := record["hash"].(string); valid {
				included[h] = true
			}
		}
	}
	indexHash, err := digest("package-index.logical.v1", normalized)
	index := document["index"].(map[string]any)
	if err != nil || indexHash != index["logical_hash"] {
		return response{}, errors.New("bad logical index hash")
	}
	content := document["content"].(map[string]any)
	roots := make([]string, 0)
	for _, root := range content["roots"].([]any) {
		text := root.(string)
		if !included[text] {
			return response{}, errors.New("root outside membership")
		}
		roots = append(roots, text)
	}
	slices.Sort(roots)
	orderedRoots := make([]any, 0, len(roots))
	for _, root := range roots {
		orderedRoots = append(orderedRoots, root)
	}
	resolution, exists := content["resolution_inputs"]
	if !exists {
		resolution = map[string]any{}
	}
	projection := map[string]any{
		"roots":                      orderedRoots,
		"dependency_policy":          content["dependency_policy"],
		"explicit_resolution_inputs": resolution,
		"index_logical_hash":         indexHash,
	}
	raw, err := encode(projection)
	if err != nil {
		return response{}, err
	}
	root, err := digest("package-content-root.v1", projection)
	if err != nil || root != content["content_root"] {
		return response{}, errors.New("bad package content root")
	}
	return response{Admitted: true, Canonical: hex.EncodeToString(raw), Index: indexHash, Root: root}, nil
}

func process(query request) (response, error) {
	if query.Mode == "package" {
		return verifyPackage(query)
	}
	value := query.Value
	switch query.Mode {
	case "bytes":
		var err error
		value, err = hex.DecodeString(query.BytesHex)
		if err != nil {
			return response{}, err
		}
	case "canonical":
	default:
		return response{}, errors.New("unknown test mode")
	}
	encoded, err := encode(value)
	if err != nil {
		return response{}, err
	}
	return response{Admitted: true, Canonical: hex.EncodeToString(encoded)}, nil
}

func main() {
	decoder := json.NewDecoder(os.Stdin)
	decoder.UseNumber()
	var queries []request
	if err := decoder.Decode(&queries); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	outcomes := make([]response, 0, len(queries))
	for _, query := range queries {
		outcome, err := process(query)
		if err != nil {
			outcome = response{}
		}
		outcomes = append(outcomes, outcome)
	}
	if err := json.NewEncoder(os.Stdout).Encode(outcomes); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
