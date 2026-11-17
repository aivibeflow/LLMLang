# 0003 — Integer Calculator

**Task ID:** `0003`  
**Difficulty:** 3 — beginner / intermediate  
**Status:** Proposed  
**Prerequisites:** 0001 — Hello, World!; 0002 — Echo  
**Related tasks:** Future parsing, error-handling, and property-testing examples

## 1. Purpose

Exercise input parsing, explicit result/error types, branching, integer arithmetic, overflow handling, and edge-case specification.

## 2. Problem Statement

Write a command-line calculator that reads one expression from standard input, evaluates it, and prints the result.

The supported expression format is:

```text
INTEGER OPERATOR INTEGER
```

The operator must be one of `+`, `-`, `*`, or `/`. The integers are signed 64-bit decimal integers. Whitespace may appear before, between, or after tokens.

Examples:

```console
$ printf '12 + 30\n' | calculator
42
$ printf '7 * -6\n' | calculator
-42
$ printf '20 / 4\n' | calculator
5
```

## 3. Behavior and Interface

### Inputs

- Read exactly one expression from standard input, terminated by LF or end-of-file.
- The expression must contain exactly three tokens: first integer, operator, second integer.
- Tokens are separated by one or more ASCII whitespace characters (space, horizontal tab, CR, or LF).
- Integer syntax: optional leading `+` or `-`, followed by one or more decimal digits. No thousands separators or radix prefixes.
- Both operands must be in the signed 64-bit range: `-9223372036854775808` through `9223372036854775807`.

### Outputs

On success:
- Print the result as a base-10 signed integer with no leading plus sign or unnecessary leading zeros.
- Print exactly one LF after the result.
- Write nothing to standard error.
- Exit with status code `0`.

On failure:
- Write one stable diagnostic line to standard error, followed by LF.
- Write no result to standard output.
- Exit with a nonzero status.

The diagnostic text is defined below so that behavior is testable:
- `invalid input\n` — malformed expression, invalid integer token, unknown operator, missing token, or extra token.
- `division by zero\n` — divisor is zero.
- `arithmetic overflow\n` — the selected operation's mathematical result is outside the signed 64-bit range, including the minimum signed value divided by -1.

### Arithmetic Semantics

- `+`, `-`, and `*` use mathematical integer arithmetic, then check that the result is in the signed 64-bit range.
- `/` performs signed integer division truncated toward zero.
- Division by zero is an error.
- The minimum signed 64-bit value divided by -1 is an overflow error.
- A nonzero remainder is discarded according to truncation toward zero. For example, `-7 / 2` produces `-3`.

## 4. Requirements

- **R-0003-01:** The program reads one expression from standard input and accepts exactly three tokens in the specified grammar.
- **R-0003-02:** The program parses both operands as signed 64-bit decimal integers and rejects values outside the permitted range.
- **R-0003-03:** The program accepts exactly the four operators `+`, `-`, `*`, and `/`.
- **R-0003-04:** Addition, subtraction, and multiplication return the mathematical result when it is within the signed 64-bit range.
- **R-0003-05:** Division truncates toward zero.
- **R-0003-06:** Division by zero produces the specified error outcome.
- **R-0003-07:** Any arithmetic result outside the signed 64-bit range produces the specified overflow outcome.
- **R-0003-08:** On success, stdout contains exactly the canonical decimal result followed by one LF, stderr is empty, and exit status is 0.
- **R-0003-09:** On failure, stdout is empty, stderr contains exactly the diagnostic corresponding to the failure followed by one LF, and exit status is nonzero.
- **R-0003-10:** Whitespace between tokens is accepted as specified; missing or extra tokens are rejected.

## 5. Constraints and Non-Goals

### Constraints

- Use LLMLang standard input/output and integer facilities.
- No third-party dependencies.
- The implementation must not rely on unchecked signed overflow.
- Parsing and arithmetic failures must be represented explicitly, not silently coerced.

### Non-Goals

- No floating-point arithmetic.
- No parentheses, precedence, or multi-operator expressions.
- No variables or assignments.
- No repeated interactive prompt.
- No arbitrary-precision arithmetic.
- No locale-specific number formats.

## 6. Acceptance Criteria

- [ ] Exactly three valid tokens are accepted, with the specified whitespace grammar. (R-0003-01, R-0003-10)
- [ ] Signed 64-bit bounds are enforced. (R-0003-02)
- [ ] All four operators produce the specified mathematical results. (R-0003-03, R-0003-04, R-0003-05)
- [ ] Division by zero is rejected with the exact diagnostic. (R-0003-06, R-0003-09)
- [ ] Overflow is rejected with the exact diagnostic, including MIN / -1. (R-0003-07, R-0003-09)
- [ ] Success and failure output channels and exit statuses match the specification. (R-0003-08, R-0003-09)

## 7. Test Scenarios

| Test ID | Scenario | Input / Action | Expected result | Requirements |
|---|---|---|---|---|
| T-0003-01 | Addition | `12 + 30\n` | stdout `42\n`, stderr empty, exit 0 | R-0003-04, R-0003-08 |
| T-0003-02 | Subtraction | `12 - 30\n` | stdout `-18\n`, stderr empty, exit 0 | R-0003-04, R-0003-08 |
| T-0003-03 | Multiplication | `7 * -6\n` | stdout `-42\n`, stderr empty, exit 0 | R-0003-04, R-0003-08 |
| T-0003-04 | Exact division | `20 / 4\n` | stdout `5\n`, stderr empty, exit 0 | R-0003-05, R-0003-08 |
| T-0003-05 | Truncate toward zero | `-7 / 2\n` | stdout `-3\n`, stderr empty, exit 0 | R-0003-05, R-0003-08 |
| T-0003-06 | Divide by zero | `1 / 0\n` | stdout empty; stderr `division by zero\n`; nonzero exit | R-0003-06, R-0003-09 |
| T-0003-07 | Addition overflow | `9223372036854775807 + 1\n` | stdout empty; stderr `arithmetic overflow\n`; nonzero exit | R-0003-07, R-0003-09 |
| T-0003-08 | Division overflow | `-9223372036854775808 / -1\n` | stdout empty; stderr `arithmetic overflow\n`; nonzero exit | R-0003-07, R-0003-09 |
| T-0003-09 | Invalid operator | `1 % 2\n` | stdout empty; stderr `invalid input\n`; nonzero exit | R-0003-03, R-0003-09 |
| T-0003-10 | Extra token | `1 + 2 3\n` | stdout empty; stderr `invalid input\n`; nonzero exit | R-0003-01, R-0003-10 |
| T-0003-11 | Whitespace | `  1\t+\t2  \n` | stdout `3\n` | R-0003-01, R-0003-10 |
| T-0003-12 | Minimum integer | `-9223372036854775808 + 0\n` | stdout `-9223372036854775808\n` | R-0003-02, R-0003-04 |
| T-0003-13 | Empty input | EOF without tokens | stdout empty; stderr `invalid input\n`; nonzero exit | R-0003-01, R-0003-09 |

## 8. Concepts Exercised

- Standard input
- Tokenization and parsing
- Signed fixed-width integers
- Algebraic result/error types
- Pattern matching / branching
- Checked arithmetic
- Deterministic formatting
- Error reporting and process exit status
- Unit and boundary testing

## 9. Completion Definition

A completed solution contains LLMLang source, tests for the listed scenarios, and execution instructions. Record parser/build/run status and any unsupported language features. Until an actual LLMLang toolchain can parse and execute it, the source must be labeled illustrative and unverified.

## 10. Implementation Notes

Prefer parsing into a typed expression/result before evaluation. Keep parse errors, division-by-zero, and arithmetic overflow distinct internally even though the external diagnostics are fixed strings. Use checked arithmetic or prove the relevant bounds before performing operations.
