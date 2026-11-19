# Research Scenario 53 — Statement Termination and Newlines

**Status:** Evidence-linked prior-art comparison; no LLMLang statement termination or layout policy selected  
**Research area:** RT-03 syntax and evaluation, RT-09 formatters/tooling  
**Updated:** 2026-11-19

## 1. Question and scope

How does source text separate statements and expressions, and can line breaks affect parsing? Keep these mechanisms distinct:

1. Explicit terminator tokens written by the author.
2. Lexically inserted terminators based on preceding token and newline.
3. Newlines treated as whitespace with grammar-controlled continuation.
4. Expression statements versus value-producing final expressions in blocks.
5. Comment/newline interaction and end-of-file behavior.
6. Formatter-preserved parse trees and automatic semicolon insertion (ASI) hazards.

This report compares Go, Rust, and Swift language references. It does not choose LLMLang syntax or claim that one line-breaking convention is universally simpler.

## 2. Prior-art comparison

### Go: token-based semicolon insertion at eligible line endings

Go's formal grammar uses semicolon terminators, while source may omit most of them. The lexer inserts a semicolon after a line's final token when that token belongs to a specified set (including identifiers, literals, `return`, `++`, `)`, `]`, and `}`). A second rule permits omission before `)` or `}`. Comments containing newlines can act like a newline for tokenization.

The finite rule produces a relatively simple grammar and conventional line-oriented source, but line breaks are semantically relevant at token boundaries. Moving an operator or brace to another line can change whether the program parses; formatter and code-generation tools must preserve the insertion points.

Sources: [Go specification — Semicolons](https://go.dev/ref/spec#Semicolons), [Go specification — Comments](https://go.dev/ref/spec#Comments).

### Rust: explicit terminators plus expression-valued blocks

Rust statements generally use semicolons, with exceptions for item declarations and block/control-flow expressions. A block may contain statements followed by an optional final expression; that final expression determines the block's value and type. A semicolon converts an expression into a statement that discards its value. Extra semicolons are permitted in specified contexts.

The terminator therefore communicates value flow as well as statement separation. This supports expression-oriented control flow and block composition, but the parser/type checker and reader must distinguish a final operand from a terminated expression statement. Line breaks alone generally do not insert a statement boundary.

Sources: [Rust Reference — Statements](https://doc.rust-lang.org/reference/statements.html), [Rust Reference — Block expressions](https://doc.rust-lang.org/reference/expressions/block-expr.html).

### Swift: optional statement semicolons, required for multiple statements on a line

Swift does not require a semicolon after each statement, though one may be written. Semicolons are required to place multiple independent statements on a single line. Newlines typically separate statements while grammar and continuation rules determine whether an expression continues.

This minimizes punctuation in ordinary source and keeps explicit same-line separation available. The language must carefully define continuation contexts so a newline can neither terminate an expression too early nor unexpectedly join two statements; formatters need to retain the intended structure.

Sources: [Swift Language Guide — The Basics](https://docs.swift.org/latest/documentation/the-swift-programming-language/thebasics/), [Swift Language Reference — Lexical Structure](https://docs.swift.org/latest/documentation/the-swift-programming-language/lexicalstructure/).

## 3. Comparison matrix

| Dimension | Go | Rust | Swift |
|---|---|---|---|
| Ordinary separator | Usually omitted; inserted semicolon token | Explicit semicolon for most statements | Usually newline/grammar; optional semicolon |
| Line break semantic role | Yes, after eligible final tokens | No generic newline terminator | Newline commonly separates, continuation grammar matters |
| Semicolon meaning | Terminates statement in grammar | Separates statements and suppresses expression value | Separates multiple statements on one line |
| Block result | Statement-oriented; explicit return/control flow | Final expression gives block value | Expression/statement rules specified by grammar; no Rust-style generic final-operand rule |
| Comment interaction | Newline-containing block comment acts like newline | Comments/whitespace do not perform general insertion | Comment/token rules and line breaks shape lexical structure |
| Main tooling risk | ASI changes after line/token movement | Missing/extra semicolon changes value/unit type | Newline continuation ambiguity and formatter decisions |

## 4. Discriminating fixtures

For each syntax candidate, parse and format the same fixtures, recording AST, statement boundaries, expression types/results, and diagnostics:

1. Move `+`, `.`, `,`, `(`, `[`, and assignment operators across line boundaries.
2. Put `else`, closing braces, and `return` expressions on adjacent/separate lines.
3. Test calls, indexing, chained method/member access, multiline argument lists, and trailing commas.
4. Insert line and block comments between tokens, including comments containing newlines and comments next to operators/braces.
5. Test empty statements, duplicate terminators, same-line statement sequences, and EOF without a final newline.
6. Compare a block's last expression with the same expression followed by a semicolon; record inferred block type and discarded effects/value.
7. Round-trip through formatter, source printer, AST serializer, and semantic diff; ensure line reflow preserves parse tree and execution.
8. Generate minimal ambiguous cases and require diagnostics to show the inserted or expected boundary.

Include newline styles (LF, CRLF), tabs, Unicode line separators if permitted by the lexer, and macros/generated source where token provenance matters.

## 5. Cross-area implications and open hypotheses

- Statement terminators and block-result semantics are separable. Choosing ASI does not require statement-oriented blocks; choosing explicit semicolons does not require every block to return a value.
- ASI moves part of the language grammar into the lexer and makes source layout relevant. The insertion rule must be short, deterministic, fully specified, and represented in parser diagnostics and source maps.
- Explicit terminators make boundaries locally visible and robust to line reflow, while adding punctuation and giving semicolons semantic weight in expression-oriented languages.
- Newline-as-separator conventions need a clear continuation rule for operators, chained calls, and nested syntax; otherwise formatting changes can create or remove program structure.
- Comments that count as newlines can create non-obvious lexical behavior. Define the interaction exactly or keep comments semantically equivalent to whitespace.
- AI-generated patches, codemods, and formatters commonly move lines or insert comments. Their correctness should be judged by AST preservation, not textual similarity.
- The parser's canonical representation should retain original spans and any synthetic tokens so diagnostics, semantic hashes, and source reconstruction can distinguish source syntax from inserted syntax.

No LLMLang statement terminator, ASI rule, newline continuation policy, or block-result rule is selected.

## 6. Next research and falsifiers

Implement the fixture corpus in two parser prototypes: an explicit-terminator grammar and a newline-sensitive lexer with a finite ASI rule. Add a third newline-separated grammar with explicit continuation conditions if Swift-like ergonomics are a candidate. Measure parse ambiguity, formatter round trips, error localization, code-generation repair rate, and accidental parse changes under line-only edits. Keep block-value behavior as an orthogonal factor.

ASI is weakened if common line wraps or comment insertions alter ASTs and users/tools miss the change. Mandatory explicit terminators are weakened if they materially increase generated source noise or repair errors without improving boundary diagnostics. Newline separation is weakened if continuation rules become context-heavy or formatters must preserve fragile line placements.

## 7. Sources and temporal limits

Official references were consulted 2026-11-19. Rust and Swift references are rolling; Go's specification is versioned. Pin language/tool versions, record raw fixtures, and compare parser behavior with documented grammar before treating observed implementation output as normative.
