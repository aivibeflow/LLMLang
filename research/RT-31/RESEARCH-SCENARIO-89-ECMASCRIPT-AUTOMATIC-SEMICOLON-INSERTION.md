# Research Scenario 89 — ECMAScript Automatic Semicolon Insertion

**Status:** Evidence-linked extension to Scenario53; no LLMLang separator policy selected
**Research area:** RT-03 syntax and control flow, RT-09 formatters/tooling
**Updated:** 2026-11-19

## 1. Question and relation to prior work

What does ECMAScript's Automatic Semicolon Insertion (ASI) actually depend on, and how does it differ from Go's fixed line-ending token set, explicit semicolon rules, and newline-separator grammars?

[Scenario 53](../RT-03/RESEARCH-SCENARIO-53-STATEMENT-TERMINATION-AND-NEWLINES.md) compares Go, Rust, and Swift. This scenario adds ECMAScript 2026 as a materially different prior-art point: the spec's insertion rules are parser/grammar driven and include restricted productions. It does not repeat the full block-result comparison or select an LLMLang policy.

## 2. ECMAScript 2026 rules

ECMAScript says most statements and declarations require a semicolon, which may be omitted in specified cases. Its normative insertion algorithm has three rules:

1. Before an offending token that cannot continue the current grammar, insertion may occur if a line terminator intervenes, the offending token is a closing brace, or the previous token is a closing parenthesis in the do-while termination case. Insertion is suppressed when it would create an empty statement or one of the two separators in a for header.
2. At end of input, a semicolon may be inserted when required to parse the goal nonterminal.
3. In a restricted production marked no LineTerminator here, a line break before the restricted token causes insertion before that token.

This is not equivalent to a lexer rule that inserts after every eligible end-of-line token. If the next line can continue a valid expression, no semicolon is inserted. For example, a line beginning with a parenthesized expression can be parsed as a call continuation of the previous expression. Conversely, the line break after return ends the return statement before its expression; a line break after throw is forbidden by a restricted production and yields a syntax error; a line break before postfix increment/decrement separates the operator from the preceding expression.

Source: [ECMAScript 2026 — Automatic Semicolon Insertion](https://tc39.es/ecma262/2026/multipage/ecmascript-language-lexical-grammar.html#sec-automatic-semicolon-insertion).

## 3. Comparison with Scenario53 profiles

| Profile | Boundary mechanism | What source movement can change |
|---|---|---|
| Go | The lexer inserts a terminator after a fixed set of token classes at line endings; a separate rule permits omission before closing parenthesis or brace. Newline-containing comments can act as a newline. | Whether an eligible token ends a statement; moving operators or braces can change parse validity. |
| Rust | Explicit semicolons separate most statements; a final block expression may produce the block's value. | A semicolon can change value flow/type; newline alone is not the generic terminator. |
| Swift | Newlines commonly separate statements under grammar continuation rules; semicolons allow multiple statements on one line. | A break can separate or continue according to expression grammar. |
| ECMAScript | Insertion occurs from parser state, end-of-input, and restricted grammar productions, subject to explicit exceptions. | Both parse boundaries and meaning can change; some line wraps preserve one expression, while others terminate a control-flow statement or make syntax invalid. |

The distinction is between token-set-driven line-end insertion and parser/grammar-driven insertion. All of these still require exact comment and line-terminator definitions.

## 4. Consequences for formatter and source tooling

For ECMAScript, a formatter cannot preserve semantics merely by preserving statement-looking line breaks. It must preserve the parse tree, including cases where a leading parenthesis, bracket, template, slash-token lexical goal, or other continuation can attach to a prior expression. It must also avoid moving a restricted token across a line terminator in return, throw, postfix update, async forms, and other no-LineTerminator-here productions.

This increases the importance of parser-backed formatting and syntax-aware source edits. A printer that chooses to emit explicit semicolons still needs to ensure the inserted tokens do not create an empty statement before else or alter a for header. Comment trivia containing a line terminator must be included in the test input, not normalized away before checking.

These are implications derived from the specification, not performance measurements of current formatters. Scenario53's requirement to compare ASTs before and after formatting remains applicable, with ECMAScript-specific lexical-goal and restricted-production metadata added.

## 5. Discriminating source pairs

A pinned ECMAScript parser/formatter profile should include paired snippets and record tokens, inserted-semicolon locations, AST, diagnostics, and execution trace where relevant:

| Pair | Expected distinction to inspect |
|---|---|
| return value / return followed by newline and value | A line terminator separates the expression from the return token; the second form returns no expression. |
| throw error / throw followed by newline and error | Restricted production: the second form is a syntax error. |
| x++ / x followed by newline and ++y | The newline prevents ++ from being the postfix operator for x. |
| a = b + c followed by newline and (d + e).print() / the same source with a semicolon after c | Without an explicit boundary, the next line may continue the call expression. |
| if (p) work() followed by newline and else other() / if (p) work(); followed by newline and else other() | Check the grammar's empty-statement exception and attachment to the if. |
| for (init; test followed by newline and ; step) | ASI must not synthesize either required for-header separator. |
| Token / block-comment / newline / token | Preserve whether a comment contains a line terminator and how that affects restricted productions. |
| LF / CRLF / ECMAScript Unicode line terminators | Confirm which code points count as LineTerminator, not just host-platform newline conventions. |

These are proposed conformance cases, not compiler or formatter runs. Pair them with Scenario87's diagnostic-span and recovery record format, but keep statement insertion distinct from async context validation.

## 6. Open questions

A candidate LLMLang policy must state whether line breaks are whitespace, terminators, or syntax interpreted by a finite lexer rule; how continuation works before opening parentheses, brackets, dots, operators, and closures; how comments affect boundaries; which constructs prohibit line breaks internally; and whether blocks yield a final expression. The formatter contract should require AST preservation, while diagnostic tests should expose inferred or missing separators.

No LLMLang statement separator, block-value rule, or formatter behavior is selected. This report is a specification comparison; no LLMLang parser tests were run.

## 7. References

- [ECMAScript 2026 — Automatic Semicolon Insertion](https://tc39.es/ecma262/2026/multipage/ecmascript-language-lexical-grammar.html#sec-automatic-semicolon-insertion)
- [Go specification — Semicolons](https://go.dev/ref/spec#Semicolons)
- [Go specification — Comments](https://go.dev/ref/spec#Comments)
- [Rust Reference — Statements](https://doc.rust-lang.org/reference/statements.html)
- [Rust Reference — Block expressions](https://doc.rust-lang.org/reference/expressions/block-expr.html)
- [Swift Language Guide — The Basics](https://docs.swift.org/latest/documentation/the-swift-programming-language/thebasics/)
- [Swift Language Reference — Lexical Structure](https://docs.swift.org/latest/documentation/the-swift-programming-language/lexicalstructure/)
