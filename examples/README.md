# LLMLang Examples

This directory contains progressively harder, implementation-independent programming tasks for LLMLang.

- [Task template](TEMPLATE.md) — required structure for every task statement.
- [0001 — Hello, World!](0001-hello-world.md)
- [0002 — Echo](0002-echo.md)
- [0003 — Integer calculator](0003-calculator.md)
- [0010 — Balance transfer](0010-balance-transfer.md)

## Directory contract

- `examples/` contains **what to build**: task statements, requirements, acceptance criteria, and black-box test scenarios.
- `draft/examples/` contains **candidate solutions**: LLMLang implementations and any implementation-specific notes or tests.
- Task IDs are stable, zero-padded four-digit numbers. Do not reuse an ID for a different task.
- A solution directory uses the same ID and slug as its task, e.g. `draft/examples/0001-hello-world/`.
- Every task statement must follow [TEMPLATE.md](TEMPLATE.md). Keep requirements observable and testable.
- Implementations must link back to the task and requirement IDs. Do not silently change task semantics to fit an implementation.
- A solution is a candidate until it can be parsed, built, and tested by an actual LLMLang toolchain. Clearly label illustrative syntax and unverified claims.

## Difficulty progression

The first tasks deliberately establish a small vertical slice:

1. **Hello, World!** — program entry point and standard output.
2. **Echo** — command-line arguments, iteration, string handling, and output formatting.
3. **Integer calculator** — parsing, algebraic result/error handling, arithmetic, overflow, and division edge cases.

Later tasks should introduce one or a small number of new concepts at a time while reusing earlier capabilities.
