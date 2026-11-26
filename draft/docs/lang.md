# LLMLang syntax

This reference covers the syntax implemented in the current checkout. The scalar MVP has a Python-shaped text frontend and a structured MCP authoring interface. The native MCP build also supports Rust-shaped syscall program bodies. A semantic profile defines the available constructs and their meaning. A dialect defines their source spelling. LLMLang supports versioned dialects that lower to a shared typed Semantic Program Graph (SPG), and the architecture leaves a default dialect open. [Architecture RFC](../RFC.md) · [Syntax dialects](../adr/022-syntax-dialects-and-shared-semantics.md)

## Scalar text source

A module contains one or more plain `def` declarations with a type annotation on every parameter and on the return value. Write `int` for signed 64-bit integers and `bool` for Booleans. Use indentation for blocks, `#` for comments, and ASCII identifiers such as `safe_divide` for portable source. Each function name must be unique within the module. [Stage 0 frontend](../../tools/llmlang_mvp/stage0/src/frontend.rs) · [Python frontend](../../tools/llmlang_mvp/frontend.py)

```python
def divide(left: int, right: int) -> int:
    if right == 0:
        builtin__fail("DivisionByZero")
    return left / right

def is_negative_half(value: int) -> bool:
    half = divide(value, 2)
    return half < 0
```

| Construct | Supported form |
| --- | --- |
| Literals | Integer literals in the signed 64-bit range, including negative literals, and `True` or `False` |
| Local binding | `name = expression` introduces a fresh name. Branches inherit the enclosing names, and their new bindings stay local to the branch. |
| Branch | `if condition:` with an optional `else:`. The condition has type `bool`. |
| Return | `return expression`. The expression must have the declared result type. |
| Explicit error | `builtin__fail("ErrorName")` or `return builtin__fail("ErrorName")`. Allowed names are `ArithmeticOverflow`, `DivisionByZero`, and `InvalidInput`. |
| Arithmetic | `+`, `-`, `*`, `/` on integers. Unary minus applies to integer literals. |
| Comparison | `==` and `!=` compare values of the same type. `<`, `<=`, `>`, and `>=` take integers. Write one comparison per comparison expression. |
| Call | `callee(arg1, arg2)` calls a declared function with typed positional arguments. The call graph must be acyclic. |

Grouping and precedence follow the Python parser. Expressions and call arguments evaluate left to right. Integer arithmetic is checked. Division truncates toward zero, division by zero produces `DivisionByZero`, and an unrepresentable result such as the minimum signed integer divided by `-1` produces `ArithmeticOverflow`. Every path must return or fail, and unreachable statements are rejected. Loops, mutation, general strings, imports, collections, and Boolean connectives in implementation bodies are outside this scalar frontend.

Lower a source file from the repository root after building Stage 0. This checks source syntax and types and prints the graph with exact implementation pins.

```sh
cargo build --locked --manifest-path tools/llmlang_mvp/stage0/Cargo.toml
tools/llmlang_mvp/stage0/target/debug/llmlang-stage0 lower \
  tools/llmlang_mvp/calculator.llmlang
```

An optional second argument supplies a JSON object mapping every declared function name to its provided contract hash, in `sha256:<64 lowercase hex digits>` form for this frontend. Use the scalar MVP CLI for contract checking and the Calculator build workflow. [Calculator source](../../tools/llmlang_mvp/calculator.llmlang) · [Scalar MVP commands](../../tools/llmlang_mvp/README.md)

## Scalar MCP authoring

The server accepts typed Change Set objects. Signatures use `i64` and `bool`. For example, a function taking `value: int` and returning `bool` has this signature.

```json
{"params":[["value","i64"]],"result":"bool"}
```

A `canonical_body` is a nonempty array of statements. The notation below uses `EXPR`, `THEN`, `ELSE`, and `REF` as placeholders.

| Kind | JSON shape |
| --- | --- |
| Integer or Boolean | `["i64", -7]` or `["bool", true]` |
| Variable | `["var", "value"]` |
| Binary expression | `["bin", "<", EXPR, EXPR]`. Uses the scalar arithmetic and comparison operators above. |
| Call | `{"callee_impl_hash": REF, "required_contract_hash": REF, "arguments": [EXPR]}`. Use an empty array for zero arguments. |
| Local binding | `["let", "name", EXPR]` |
| Return | `["return", EXPR]` |
| Explicit error | `["fail", "DivisionByZero"]`. Uses the same set of labels as the text frontend. |
| Branch | `["if", EXPR, THEN, ELSE]`. Each branch is an array of statements. `THEN` is nonempty and `ELSE` may be empty. |

Use an existing server identity (64 lowercase hex digits) or `{"local":"request-id"}` for an object created in the same Change Set. A call pins both the callee implementation and the contract the caller relies on. A function separately pins its provided contract. An exported interface names its public contract, and a version binding selects the implementation. Use the identities returned by the server for MCP calls and resource reads. The scalar text frontend's graph JSON uses its own encoding, including a positional call tuple. [Server schemas](../src/server/main.rs) · [Runnable MCP examples](server.md)

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

Predicate values can be JSON Booleans or Boolean expression strings. The predicate language supports comparisons, including chains, `and`, `or`, `not`, and mathematical integer `+`, `-`, `*`, and unary minus. Use `quotient(a, b)` for the totalized quotient, which truncates toward zero and returns zero when `b` is zero. Program arithmetic can fail. The example rules apply to the `divide` signature with `left` and `right` as `i64`. The precondition excludes the signed division overflow case. [Scalar Contract IR](../../tools/llmlang_mvp/CONTRACT-IR.md) · [Server rule adapter](../server/scalar.py)

## Other implemented source profiles

The archived Stage 0 guest workflow used a separate package snapshot and typed syscall operations. Its package CLI and fixtures are available at the revision that shipped them. [Archived syscall package](https://github.com/aivibeflow/LLMLang/blob/744aaf3f98e357a5375b55a67a538d7295d3608c/packages/linux.syscalls/README.md)

The `program`, `effects`, and `operation` forms in the draft Hello, Echo, and Calculator sketches are illustrative notation. For executable scalar text, start with `def`. [Draft examples and status](../examples/README.md)

The native MCP build reads committed SPG packages. In the [native Echo example](../examples/0004-syscall-echo/main.llmlang), the source has leading syscall imports and a Rust-shaped `pub fn main() -> ExitStatus` with a braced body. The Copy example uses `pub fn main(args: LaunchArgs) -> ExitStatus`. The package stores the source block in the function row and the canonical signature in `function_signatures`. Call compatibility obligations identify the exact callee and required contract. Built-in function names start with `builtin__`. The imported syscall functions call `stdlib::syscall`, which invokes `builtin__syscall`. Hello World imports `stdlib.write` and passes a UTF-8 string. [Native examples](../examples/README.md#linux-syscall-program-packages) · [Build through MCP](server.md#build-an-existing-native-program)
