# 0003 — Integer Calculator

The LLMLang body for [Task 0003](../../../examples/0003-calculator.md) is
stored as `canonicalBody` in [functions.json](functions.json). The package
exports a parameterless `main() -> ExitStatus`.

## Build and run

Start the [MCP server](../../docs/bootstrap.md#build-and-run-native-examples)
on Linux x86-64. Use `import_package` to import `draft/builtin`, `draft/stdlib`,
`draft/examples/linux.syscalls`, and `draft/examples/0003-calculator` in
that order. Call `build_package` with the calculator's returned
`snapshot_id` and target `linux-x86_64`. Run the returned artifact.

```sh
printf '20 / 4\n' | /path/to/artifact
# 5
```

| Requirements | Implementation |
|---|---|
| R-0003-01, R-0003-10 | Read descriptor 0 through the first LF or EOF. Split the record on spaces, tabs and CR, and require exactly three tokens. |
| R-0003-02, R-0003-03 | Parse optional signs and ASCII decimal digits with checked accumulation. Dispatch only the four supported operators. |
| R-0003-04 to R-0003-07 | Use checked signed 64-bit operations. Division truncates toward zero. Zero divisors and arithmetic overflow produce distinct failures. |
| R-0003-08, R-0003-09 | Write the canonical decimal result and LF to descriptor 1 with status 0, or the specified diagnostic and LF to descriptor 2 with status 1. |

The [native MCP test](../../server/tests/native_build_e2e.py) builds the package
and checks stdout, stderr and exit status for all thirteen task scenarios,
the additional RT-01 Calculator cases, input across a read-buffer boundary,
LF termination and a failed write. Native import and build report
`verification_status: "unchecked"`.
