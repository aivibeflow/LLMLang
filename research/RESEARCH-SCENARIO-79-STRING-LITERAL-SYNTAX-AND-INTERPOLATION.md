# Research Scenario 79 — String Literal Syntax and Interpolation

**Status:** Evidence-linked prior-art comparison; no LLMLang literal syntax selected
**Research area:** RT-03 lexical and value semantics, RT-09 diagnostics/tooling, RT-18 text safety
**Updated:** 2026-11-19

## 1. Question and boundary

How should source text encode runtime string/byte values, multiline text, delimiter escapes, Unicode escapes, and interpolation? Scenario 46 compares runtime text representations, encoding, indexing, equality, and normalization; this study compares the source-language boundary from spelling to literal value. It also asks whether interpolation is lexical sugar, a typed builder protocol, or absent from the core language.

This is a specification survey, not a lexer implementation study. It does not settle runtime string/Bytes types, formatting APIs, template escaping for HTML/SQL/shell, or localization.

## 2. Prior-art comparison

### Rust: ordinary escaped forms plus hash-delimited raw forms; formatting is a separate macro/API

Rust ordinary string literals use escapes, including Unicode scalar escapes. Raw literals use `r` plus a chosen count of `#` delimiters, so content can include quote/backslash sequences without interpretation until the matching terminator. Separate byte-string forms constrain content to ASCII and produce bytes rather than Unicode text; raw-byte strings retain the delimiter-count scheme. Multiline source newlines are possible in ordinary/raw forms subject to lexical rules. The formatting facility is `format!`/format arguments rather than interpolation embedded in the base string-token grammar.

This separates text, byte payload, and formatting syntax. Delimiter hashes handle nested quotes robustly, while multiple literal families enlarge lexical grammar and require the formatter/parser to distinguish format strings from ordinary values.

Source: [Rust Reference — Tokens, string and byte-string literals](https://doc.rust-lang.org/reference/tokens.html#literals).

### Go: interpreted double quotes and raw backquotes with precise byte-producing escapes

Go has interpreted double-quoted literals and raw backquoted literals. Raw contents preserve backslashes and newlines, except carriage returns are removed. Interpreted literals support Unicode and byte escapes; notably `\xNN` and three-digit octal escapes contribute individual bytes, while Unicode escapes encode characters as UTF-8. The specification rejects invalid Unicode scalar escapes such as surrogate values. Go has no built-in interpolation syntax; formatting is performed by library calls such as `fmt.Sprintf`.

This provides a very legible raw form and makes byte escapes useful for protocol data, but raw backticks cannot contain a backtick and newline normalization is a semantic detail authors may overlook. A string literal can contain arbitrary bytes even though source text is UTF-8.

Sources: [Go specification — String literals](https://go.dev/ref/spec#String_literals), [Go `fmt` package](https://pkg.go.dev/fmt).

### Swift: escaped and triple-quoted multiline strings, hash delimiters, typed interpolation

Swift supports single-line escaped strings and triple-quoted multiline strings. The multiline delimiter excludes the opening and closing delimiter line breaks, has indentation rules, and can represent a boundary newline through a blank first/last line. Extended delimiters add one or more `#` symbols; the matching count controls whether backslashes, interpolation, and quote sequences are active. Interpolation uses `\(expression)`, and the standard `StringInterpolationProtocol` lowers interpolation segments to typed `appendInterpolation` calls that can be overloaded.

This combines readable templates, raw-delimiter control, multiline indentation, and typed extensibility. Overloaded interpolation means apparent textual formatting can invoke user-defined code and have effects or custom semantics. That is an API/compiler behavior dimension, not just a lexer decision.

Sources: [Swift Language Reference — String Literals](https://docs.swift.org/latest/documentation/the-swift-programming-language/lexicalstructure/#String-Literals), [Swift — String interpolation](https://docs.swift.org/latest/documentation/the-swift-programming-language/stringsandcharacters/#String-Interpolation), [Swift `StringInterpolationProtocol`](https://docs.swift.org/latest/documentation/swift/stringinterpolationprotocol/).

### Zig: byte-oriented quoted literals and no-escape multiline form

Zig string literals are byte-oriented (sentinel-terminated byte arrays in the documented examples). Escapes distinguish byte escapes such as `\\xNN` from Unicode code point escapes that are UTF-8 encoded. A surrogate escape can represent bytes that are not valid Unicode scalar UTF-8 according to the current master reference, so byte and text validity must remain distinct. Multiline strings use a line-leading `\\` marker; the form has no escapes, removes the marker/newline convention, and continues across lines when the next line begins with the marker. Formatting is done through explicit formatting APIs, not inline interpolation.

This keeps multiline templates literal and byte representation explicit, while making indentation/line marker rules unusual and requiring callers to identify text validity themselves.

Source: [Zig language reference — String Literals, Escape Sequences, and Multiline String Literals](https://ziglang.org/documentation/master/#String-Literals).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Zig |
|---|---|---|---|---|
| Basic literal | Escaped double-quoted text | Escaped double-quoted interpreted string | Escaped double-quoted string | Escaped byte string |
| Raw form | `r###"…"###` matching hash count | Backquotes; cannot contain backquote | `#"…"#` matching hash count | Multiline `\\`-prefixed lines; no escapes |
| Multiline | Raw and regular token rules allow line-break cases | Raw form allows newlines; CR stripped | Triple quotes with indentation and boundary newline rules | Line-marker form; line continuation rule determines inserted newline |
| Byte literal family | Explicit byte and byte-string tokens, ASCII-limited | Byte escapes can produce arbitrary string bytes | String is Unicode-oriented; byte construction is separate | String literal is byte sequence; `\\xNN` explicit |
| Unicode escape | `\\u{...}` scalar escapes | `\\uNNNN` / `\\UNNNNNNNN`, rejects invalid scalar values | `\\u{...}` scalar escape | `\\u{...}` UTF-8 encoding; current master permits surrogate values as a byte-oriented exception |
| Interpolation | Formatting macros/library, not built-in string interpolation | Formatting function/package | Built-in `\\(expr)`; typed/overloadable interpolation protocol | Formatting API, no interpolation in string token |
| Main advantage | Explicit text/bytes and robust raw delimiters | Simple raw form and exact byte escapes | Readable templates and typed interpolation | Byte-level control, no-escape multiline source blocks |
| Main cost | More literal token families and macro-format distinction | Backtick limitation, CR stripping, no inline interpolation | Interpolation may call user code; indentation rules | Less conventional multiline syntax and text-validation burden |

The matrix describes current documentation surfaces; library/runtime versions and language editions should be pinned in any prototype.

## 4. Discriminating parser and authoring corpus

1. Escape every delimiter and control character: quote, slash, backslash, NUL, tab, CR/LF, and line continuation.
2. Embed the raw terminator inside content, including quotes followed by varying counts of hashes/backticks.
3. Test multiline beginning/ending newlines, indentation at several columns, CRLF source files, tabs, blank lines, and trailing whitespace.
4. Compare `\\xFF`, Unicode scalar escapes, literal non-ASCII, and multi-byte UTF-8 to byte-for-byte expected values; include surrogate and out-of-range escapes.
5. Ensure interpolated expression braces/parens, nested string literals, quotes, raw delimiters, and multiline expressions parse without confusing the host lexer.
6. Interpolate strings, numbers, secrets, untrusted input, and values with custom formatting behavior. Record whether conversion is explicit, typed, locale-sensitive, or user-overloadable and whether evaluation has effects.
7. Test source containing strings that look like HTML, SQL, shell, regex, JSON, and LLMLang syntax; verify there is no implicit context-specific escaping.
8. Round-trip through formatter, syntax highlighting, parser recovery, semantic tree serialization, and source generation; malformed/unterminated cases should yield local diagnostics rather than swallowing the rest of the file.
9. Check literal length/compile-time resource limits and diagnostic spans for escape errors and interpolation holes.

## 5. LLMLang candidate axes and safety implications

- **L-A Minimal escaped text plus explicit Bytes:** one canonical decoded value representation, explicit raw-delimiter syntax when necessary, and no special byte escapes in text literals.
- **L-B Paired escaped/raw text and byte literals:** ergonomic templates and binary fixtures at the cost of a larger lexer grammar and more type distinctions.
- **L-C Text literals with typed interpolation:** interpolation holes are AST expressions with explicit conversion policy; inspect whether custom append protocols are allowed in core or only libraries.
- **L-D No inline interpolation; explicit formatter/template APIs:** clear type/evaluation boundaries and fewer injection surprises, with additional syntax for common messages.
- **L-E Context-typed templates:** separate safe template types for HTML/SQL/command contexts; safe only if escaping/context transitions are represented in types and cannot be skipped accidentally.

These axes can combine and are not recommendations. Interpolation does not automatically escape for a destination grammar. A value formatted into SQL, HTML, shell, regex, or source code remains a separate context-specific security problem. If LLMLang supports interpolation, specify expression evaluation order, conversion dispatch, locale, failure/error propagation, effects, and whether source interpolation can invoke arbitrary user code. Literal decoding must also align with Scenario 46's distinction between valid Text and arbitrary Bytes.

## 6. Open questions and falsifiers

- Are raw strings delimiter-counted, escaped, or absent? Can they represent their own terminator?
- Are multiline indentation trimming and CRLF normalization part of literal value semantics or formatter-only behavior?
- Are Unicode escapes restricted to scalar values in Text literals, with separate explicit byte escapes for malformed/non-text sequences?
- Does interpolation call user-defined conversion code, use a closed set of built-in formatters, or remain a library facility?
- Is interpolation typed by destination context, or is every result a plain string requiring a separately typed safe-template API?
- How do interpolation errors/effects behave inside expressions, async functions, and const evaluation?
- What syntax does source generation use to quote arbitrary values safely and produce minimal, stable diffs?

The delimiter-counted raw form is weakened if it produces confusing editor highlighting or pathological lexer behavior. A single-quote escaped form is weakened if source generators routinely emit incorrect escape sequences. Inline interpolation is weakened if its hidden conversions/effects are hard to review or security reviews mistake it for automatic escaping. No LLMLang literal or interpolation rule is selected.

## 7. Evidence quality and temporal limits

Official references were consulted 2026-11-19. Rust and Swift documentation is rolling; Go's language spec is edition/version-sensitive; Zig master documentation changes quickly. The Zig surrogate escape detail is particularly important to confirm against the pinned release used for implementation. No parser, formatter, or compiler was executed for this report.
