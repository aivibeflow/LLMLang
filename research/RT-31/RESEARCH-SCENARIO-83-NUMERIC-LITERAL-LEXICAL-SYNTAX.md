# Research Scenario 83 — Numeric Literal Lexical Syntax

**Status:** Evidence-linked prior-art comparison; no LLMLang numeric token grammar selected  
**Research area:** RT-03 lexical and expression semantics, RT-04 literal typing, RT-11 parser/compiler compatibility  
**Updated:** 2026-11-19

## 1. Question and scope

Which source spellings form integer and floating-point literal tokens, and how should a lexer distinguish them from operators, identifiers, and adjacent punctuation? This study concerns lexical grammar and token boundaries: radix prefixes, digit separators, decimal/hex exponents, decimal points, suffixes, signs, imaginary forms, and malformed-number recovery.

It is separate from [Scenario 73](RESEARCH-SCENARIO-73-NUMERIC-LITERAL-TYPING-AND-CONVERSIONS.md), which studies contextual typing, exact compile-time values, defaulting, and conversions; and [Scenario 78](RESEARCH-SCENARIO-78-FLOATING-POINT-REPRODUCIBILITY-AND-IEEE-EDGES.md), which studies runtime float semantics, special values, fusion, and reproducibility. This report does not decide numeric value representation or type inference.

## 2. Prior-art comparison

### Rust: radix-prefixed integers, decimal floats, typed suffixes, sign as operator

Rust supports decimal, binary (`0b`), octal (`0o`), and hexadecimal (`0x`) integer forms, digit separators, decimal floating-point point/exponent forms, and suffixes such as `i32`, `u8`, `f64`. Suffix spelling is permissive at the token level for macro input; expression parsing later restricts valid suffixes. `-1i8` is two tokens, unary `-` plus the literal. A trailing decimal point is a float in selected contexts (`2.`), but `2.f64` is parsed as method syntax rather than a suffixed float, demonstrating a lexer/parser boundary.

Source: [Rust Reference — Tokens, Number literals](https://doc.rust-lang.org/reference/tokens.html).

### Go: binary/octal/hex integers, decimal and hexadecimal floats, imaginary suffix

Go supports decimal, binary, octal, and hexadecimal integers with underscores only after a base prefix or between digits. Decimal floats permit an omitted integer or fractional part (`.25`, `1.`), while hexadecimal floats use `p`/`P` binary exponents; the exponent is required for hex floats. Imaginary literals append `i` to integer or float forms. `0x15e-2` is an integer followed by subtraction because hexadecimal `e` is a digit, while `0x1p-2` is a hex float. The sign remains an operator, not part of the numeric literal.

Source: [Go specification — Integer, floating-point, and imaginary literals](https://go.dev/ref/spec#Integer_literals).

### Swift: arbitrary-precision literal syntax, decimal/hex float forms, minus in signed float grammar

Swift integers support decimal, binary, octal, and hexadecimal prefixes, with underscores for grouping and leading zeroes that do not imply octal. Floating literals support decimal and hexadecimal (`p` exponent) forms. The lexical reference describes a signed floating-point literal grammar with optional `-`, while its prose describes negative literals as a prepended minus sign; parser/AST representation and operator semantics must therefore be checked separately before treating sign as literal payload. Numeric literal defaulting and contextual conversion are outside this study.

Source: [Swift Language Reference — Lexical Structure](https://docs.swift.org/latest/documentation/the-swift-programming-language/lexicalstructure/).

### Zig: separators between digits and decimal/hex floats with comptime literal forms

Zig documents radix-prefixed integers and decimal/hex float examples such as `0x103.70p-5`; underscores separate pairs of digits in numeric examples. Float tokens have the compile-time `comptime_float` type, while integer literals are `comptime_int`, connecting lexical forms to a dedicated compile-time numeric model. Zig's rolling master documentation should be pinned before using exact edge rules as a language comparison.

Source: [Zig Language Reference — Integer literals and Float literals](https://ziglang.org/documentation/master/#Integer-Literals).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Zig |
|---|---|---|---|---|
| Integer bases | 2, 8, 10, 16 | 2, 8, 10, 16 | 2, 8, 10, 16 | 2, 8, 10, 16 |
| Leading zero policy | Decimal unless explicit radix prefix | `0` decimal; `0o` octal; legacy leading-zero edge for imaginary spelling | Leading zeroes do not change base | Decimal unless explicit radix prefix |
| Digit separators | `_` in grammar with some permissive placements | After base prefix or between successive digits | `_` between digits | `_` between two digits in cited examples |
| Decimal float forms | `digits.digits?`, or `digits exponent` | Integer/fractional part may be omitted; point or exponent may be omitted | Decimal fraction and optional exponent | Decimal fraction/exponent |
| Hex float forms | Not in cited numeric-token grammar | `0x` mantissa plus required `p` exponent | `0x` with optional hex fraction and required `p` exponent | Hex mantissa examples with `p` exponent; current master docs |
| Suffixes | Integer/float type suffixes; token-level arbitrary suffix for macros | Imaginary `i`; otherwise type is contextual | No general source numeric type suffix shown in cited grammar | No type suffix needed in cited examples; comptime literal types |
| Sign tokenization | `-` separate operator | `-` separate operator | Reference grammar has optional sign for float literal; semantics should be separated | Unary `-` expression in examples |
| Special distinguishing edge | `2.` is float; `2.f64` is method-like | `0x15e-2` integer minus 2; `1.e+0` float | Hex float `0xFp-2`; leading zero is decimal | Hex float `0x103.70p-5`; no source NaN/Inf syntax |

## 4. Discriminating lexer/parser fixtures

1. Tokenize `1`, `1.`, `.1`, `1.e2`, `1e2`, `1..2`, `1.foo`, `1.f32`, `1e`, and `1e+`.
2. Compare radix ambiguity: `0`, `00`, `0o7`, `0xFF`, `0x1e-2`, `0x1p-2`, `0x1.2p-2`, and malformed prefixes such as `0x.p1`.
3. Exercise separators at every location: `1_000`, `_1`, `1_`, `0x_FF`, `0xFF_`, `1_.2`, `1._2`, `1.2_e3`, and `1.2e_3`.
4. Test suffix/identifier boundaries: `42u8`, `42foo`, `1f32`, `1e3f32`, `1efoo`, `1_i32`, and adjacent Unicode identifier start characters.
5. Confirm sign splitting with `-1`, `--1`, `1-2`, `1e-2`, `-0.0`, and minimum signed value spellings. Record token stream separately from parser AST.
6. Include imaginary/complex feature cases such as `0i`, `1.0i`, `0x1p-2i`, and adjacency to identifier `imaginary`.
7. Feed each malformed form through parser recovery and formatter/source-emitter round trips. Confirm errors cover the intended malformed token rather than silently splitting into a different valid expression.

For every fixture, capture token kind, raw spelling, decoded exact value if available, suffix, source span, parser interpretation, and error-recovery boundary. Run one lexer implementation against a hand-built corpus before considering cross-compiler behavioral claims.

## 5. Candidate axes and implications

- **Radix set:** decimal only; decimal plus binary/hex; or all common bases including octal. Prefix choice should not make leading-zero decimal ambiguous.
- **Digit grouping:** underscore only between digits, or more permissive grouping. Restrictive grouping makes malformed numbers easier to diagnose consistently.
- **Decimal point:** permit `.5`, `1.`, both, or neither. This interacts with member access, ranges, and field selection.
- **Hex floats:** omit for simplicity, or support explicit binary exponent `p`; exact hex significands are useful for bit-exact constants but require clear mandatory exponent rules.
- **Type suffix:** no suffix with contextual typing; selected fixed suffixes; or permissive lexer suffix plus parser/macro interpretation. Tokenization should be independent of final type validity.
- **Sign:** always operator, or signed numeric token forms for selected literals. Operator form composes cleanly with expressions but needs precise minimum-integer handling.
- **Additional numeric domains:** imaginary literal suffixes or other forms are separate language features, not required for ordinary real-number token grammar.

The same source text can tokenize differently around `.` and `e` depending on radix and exponent rules. These choices affect parser ambiguity, syntax highlighting, macro/token APIs, error recovery, formatters, code generators, and source maps. Canonical spelling and exact value interpretation should not be conflated with lexical token identity.

## 6. Open questions and falsifiers

- Are binary/octal prefixes needed as first-class source syntax, and should octal be included alongside binary/hex?
- Is underscore placement restricted to between digits, including exponent and radix prefixes?
- Should `.5` or `1.` be accepted, given interactions with ranges, member access, and statement terminators?
- Are hexadecimal floating literals needed, and must their `p` exponent be present?
- Are numeric suffixes type selectors, merely lexical token data, or disallowed in ordinary source?
- Is unary minus always a distinct operator, including on `2^N` boundary literals?
- What error policy prevents a malformed numeric run from being reinterpreted as a different sequence of valid tokens?
- Are imaginary literals within language scope or better represented by ordinary complex APIs/operators?

Permissive separators are weakened if they make typos look like valid token splits. A restricted decimal-only syntax is weakened if exact bit-level constants and low-level code are common workloads. Hex floats are weakened if readability suffers and target-independent exact constant needs are already served by typed bit constructors. Suffix-heavy forms are weakened if they duplicate contextual typing and destabilize edits. Signed-token syntax is weakened if it diverges from ordinary operator precedence or breaks compositional parser behavior.

No numeric token grammar, suffix policy, radix set, or sign model is selected.

## 7. Sources and temporal limits

Primary language references were consulted on 2026-11-19. Rust Reference, Swift 6.4 docs, Go specification, and Zig master are living documents; Zig master is especially version-sensitive. Pin exact versions before conformance tests. This is analytical specification comparison; no target lexer was benchmarked.
