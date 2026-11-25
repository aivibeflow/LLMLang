# RT-04 contextual inference and explicit generic type boundaries

**Date** 2026-11-25 · **Plan** §5.1 · **Issue** [#324](https://github.com/aivibeflow/LLMLang/issues/324)

The fixture compiles nine corresponding Rust and Go cases. A generic producer returns the default value of a type parameter with no value parameters. Cases vary where the caller provides expected type information. A generic identity function supplies an argument-inference and default-literal control.

| Context | Rust 1.85.1 | Go 1.23.6 |
| --- | --- | --- |
| Explicit type argument | Accepts `u16` | Accepts `uint16` |
| Call result assigned to an annotated local | Infers `u16` | Cannot infer the type argument |
| Call result returned from an annotated function | Infers `u16` | Cannot infer the type argument |
| Generic function value assigned to a typed function variable | Infers `u16` | Infers `uint16` |
| Generic identity given a typed argument | Preserves `u16` | Preserves `uint16` |
| No type context | Refuses ambiguous inference | Refuses missing type inference |
| One local used at two incompatible types | Refuses incompatible expected types | Refuses missing call-site inference |
| Unannotated literal through identity | Defaults to `i32` | Defaults to `int` |
| Explicit public type after a private type edit | Both implementations expose `u16` | Both implementations expose `uint16` |

Twelve of 18 compilation judgments admit the program, and every admitted native output displays the independently expected type and value. Typing a function value can provide evidence unavailable to a direct result-only call in this Go profile. The public annotation and explicit conversion preserve the declared API type while allowing an implementation-local type change.

An LLMLang candidate can distinguish inference from arguments, result context, function-value context and literal defaults. It can make unresolved or conflicting obligations explicit at the boundary. The fixture covers one generic result relationship in each language. Principality, bidirectional elaboration across effects and subtyping, source-level migration, and canonical LLMLang inference remain open.

Reproduce with Rust 1.85.1, Go 1.23.6 and CPython 3.12.14 from the repository root.

```bash
study=research/language-design/RT-04/GENERIC-CONTEXT-INFERENCE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent builds reproduced compile decisions and observed native results.
