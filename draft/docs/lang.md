# LLMLang syntax

This reference covers the syntax implemented in the current checkout. The scalar verifier accepts structured MCP Change Sets. The native profile uses Rust-shaped syntax with braced function bodies. A semantic profile defines the available constructs and their meaning. A dialect defines their source spelling. LLMLang supports versioned dialects that lower to a shared typed Semantic Program Graph (SPG), and the architecture leaves a default dialect open. [Architecture RFC](../RFC.md) · [Syntax dialects](../adr/022-syntax-dialects-and-shared-semantics.md)

## Scalar MCP authoring

The server accepts typed Change Set objects. Signatures use `i64` and `bool`. For example, a function taking a signed 64-bit integer and returning a Boolean has this signature.

```json
{"params":[["value","i64"]],"result":"bool"}
```

A `canonical_body` is a nonempty array of statements. The notation below uses `EXPR`, `THEN`, `ELSE`, and `REF` as placeholders.

| Kind | JSON shape |
| --- | --- |
| Integer or Boolean | `["i64", -7]` or `["bool", true]` |
| Variable | `["var", "value"]` |
| Binary expression | `["bin", "<", EXPR, EXPR]`. Uses the operators described below. |
| Call | `{"callee_impl_hash": REF, "required_contract_hash": REF, "arguments": [EXPR]}`. Use an empty array for zero arguments. |
| Local binding | `["let", "name", EXPR]` |
| Return | `["return", EXPR]` |
| Explicit error | `["fail", "DivisionByZero"]`. Represents `builtin__fail` and is allowed by the server only in `builtin`. Supported labels are `ArithmeticOverflow`, `DivisionByZero`, and `InvalidInput`. |
| Branch | `["if", EXPR, THEN, ELSE]`. Each branch is an array of statements. `THEN` is nonempty and `ELSE` may be empty. |

Use an existing server identity (64 lowercase hex digits) or `{"local":"request-id"}` for an object created in the same Change Set. A call pins both the callee implementation and the contract the caller relies on. A function separately pins its provided contract. An exported interface names its public contract, and a version binding selects the implementation. Use the identities returned by the server for MCP calls and resource reads. Direct calls must form an acyclic graph. [Server schemas](../src/server/main.rs) · [Runnable MCP examples](server.md)

Scalar arithmetic supports checked `+`, `-`, `*`, and `/` on signed
64-bit integers. Division truncates toward zero. A zero divisor produces
`DivisionByZero`. An unrepresentable result produces `ArithmeticOverflow`.
Equality operators `==` and `!=` require operands of the same type.
Ordering operators `<`, `<=`, `>`, and `>=` require integers.
Branch conditions have type `bool`, and every path must return or fail.

### Contract rules

A `put_contract` operation takes a typed signature and an array of rules. `requires` and `ensures` have a `predicate`. `error_declaration` has an `error_label`. An `error_guard` has both and refers to a declared error. Multiple predicates for one outcome are conjoined. An error declaration with no guards admits that error anywhere in the contract's input domain. Optional `user_request_texts` records the request prose alongside the formal rules. Use parameter names in all predicates and `result` in `ensures`. The contract parser reserves `result` and `quotient` as parameter names.

```json
[
  {"kind":"requires","predicate":"left >= 0"},
  {"kind":"ensures","predicate":"result == quotient(left, right)"},
  {"kind":"error_declaration","error_label":"DivisionByZero"},
  {"kind":"error_guard","error_label":"DivisionByZero","predicate":"right == 0"}
]
```

Predicate values can be JSON Booleans or Boolean expression strings. The predicate language supports comparisons, including chains, `and`, `or`, `not`, and mathematical integer `+`, `-`, `*`, and unary minus. Use `quotient(a, b)` for the totalized quotient, which truncates toward zero and returns zero when `b` is zero. Program arithmetic can fail. The example rules apply to the `divide` signature with `left` and `right` as `i64`. The precondition excludes the signed division overflow case. [Historical Scalar Contract IR](https://github.com/aivibeflow/LLMLang/blob/138ba12f754967c9fbc6c0adbf29fc8d591836a3/draft/llmlang_mvp/CONTRACT-IR.md) · [Server rule adapter](../server/scalar.py)

## Native source syntax

Place imports before function declarations. In an import, the last dot separates the package name from the function name. For example, write `import stdlib.write` or `import linux.syscalls.write`. Both examples call `write(...)` in the function body. [Hello World](../examples/0001-hello-world/functions.json) · [Syscall Hello World](../examples/0009-syscall-hello-world/functions.json)

Function declarations use `fn`, parameter types follow their names, and a return type follows `->`. The public entry point is `pub fn main() -> ExitStatus` or `pub fn main(args: LaunchArgs) -> ExitStatus`. The function body is enclosed in braces. [Entry point](../adr/032-program-package-main.md) · [Copy example](../examples/0005-syscall-copy/functions.json)

Built-in function names start with `builtin__`. Only code in the `builtin` package can reference them directly. Native calls such as `builtin::syscall` resolve through exact package bindings. [Built-in names and visibility](../adr/034-built-in-function-prefix.md)
