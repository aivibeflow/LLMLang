# 0001 — Hello, World!

The function body for [Task 0001](../../../examples/0001-hello-world.md) is in
[`functions.json`](functions.json). Import `draft/builtin`. Then import and build this package with MCP for `linux-x86_64`.

| Requirements | Implementation |
|---|---|
| R-0001-01 to R-0001-03 | `main()` sends the exact UTF-8 greeting and line feed to descriptor 1 through `builtin.write` and returns zero on success. |
| R-0001-04 | `main()` returns 1 if writing fails. |
| R-0001-05 | The entry point takes no launch arguments and reads no input. |

The [native MCP test](../../build/server/tests/native_build_e2e.py) builds and
executes the package, checks the exact output with and without arguments
or input, and tests the write failure with `/dev/full`. Native imports and
builds report verification status `unchecked`.
