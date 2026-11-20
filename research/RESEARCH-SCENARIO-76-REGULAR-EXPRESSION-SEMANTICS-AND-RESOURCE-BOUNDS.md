# Research Scenario 76 — Regular-Expression Semantics and Resource Bounds

**Status:** Evidence-linked prior-art comparison; no LLMLang regex syntax or execution policy selected  
**Research area:** RT-03 text processing semantics, RT-09 standard-library/runtime contracts, RT-16 untrusted-input security  
**Updated:** 2026-11-19

## 1. Question and scope

Which regex dialect and matching engine should LLMLang expose, and what resource guarantees apply to untrusted patterns or inputs? Separate accepted syntax, leftmost/ordered matching and capture semantics, Unicode character classes, worst-case time/space, and timeout/cancellation behavior. Scenario 46 compares string encodings/index units and explicitly leaves regular expressions open. This report treats regex as an API/runtime contract, not just a parser feature.

## 2. Prior-art comparison

### Rust: ecosystem regex crate with bounded engine and deliberate syntax exclusions

Rust has no regex engine in its core language; the commonly used `regex` crate provides Unicode-aware regular expressions by default. It uses finite-automata techniques and gives worst-case `O(m*n)` bounds for a single search (`m` pattern size, `n` haystack size); repeated-match iterator APIs can have higher `O(m*n^2)` worst-case behavior. To retain these bounds, it excludes constructs such as look-around and backreferences that require a different engine strategy. The crate documents Unicode tables and options to disable selected Unicode support to reduce binary/compile costs.

Source: [Rust `regex` crate documentation](https://docs.rs/regex/latest/regex/).

### Go: standard RE2-compatible dialect with linear input-time guarantee

Go's standard `regexp` package accepts an RE2-compatible syntax and guarantees execution linear in input size for a fixed expression. The syntax intentionally lacks backreferences and look-around. This provides a strong predictable-runtime default in the standard library, with a feature trade-off for expressions that rely on those constructs. The guarantee applies to matching time; pattern compilation, repeated result materialization, and application-level loops should still be measured and bounded separately.

Sources: [Go `regexp` package](https://pkg.go.dev/regexp), [Go `regexp/syntax` package](https://pkg.go.dev/regexp/syntax).

### .NET: feature-rich backtracking engine plus explicit nonbacktracking mode

.NET's default engine uses backtracking and supports a rich dialect, including constructs such as lookarounds and backreferences. The documentation warns that optional quantifiers and alternation can cause catastrophic backtracking, and recommends timeouts for backtracking on untrusted input. `RegexOptions.NonBacktracking` provides an alternate engine with a linear-time guarantee in input length, but excludes constructs that depend on backtracking. This makes the safety/performance choice an explicit API option rather than forcing one engine profile on all callers.

Sources: [.NET Regex options — NonBacktracking](https://learn.microsoft.com/en-us/dotnet/standard/base-types/regular-expression-options#nonbacktracking-mode), [.NET Backtracking and timeouts](https://learn.microsoft.com/en-us/dotnet/standard/base-types/backtracking-in-regular-expressions).

### Swift Foundation: ICU-compatible Unicode regex API

Foundation's `NSRegularExpression` is documented as conforming to ICU's regex specification and applies compiled expressions to Unicode strings. Its API exposes Unicode-sensitive classes, boundaries, captures, and match ranges. The cited API documentation does not establish the same linear-time guarantee as Go or Rust's `regex` crate, so a language-level or standard-library contract should not infer bounded execution merely from the engine's Unicode support or API shape. Callers need an explicit resource limit or an engine profile when patterns/input are untrusted.

Source: [Apple Foundation — `NSRegularExpression`](https://developer.apple.com/documentation/foundation/nsregularexpression).

## 3. Candidate policies

| Candidate | Dialect and resource policy | Trade-offs |
|---|---|---|
| RX-A — Linear-time dialect by default | Standard engine forbids backreferences/look-around or other unbounded constructs; document a worst-case bound. | Safer for untrusted input and reproducible latency; some familiar patterns need reformulation. |
| RX-B — Backtracking with required limits | Rich dialect; every call accepts a mandatory time/fuel/cancellation budget and reports limit exhaustion distinctly. | Broad compatibility and expressive captures; limits may interrupt otherwise valid matches and resource accounting must be portable. |
| RX-C — Dual explicit engines | Provide safe bounded and feature-rich engines under different APIs/modes; pattern validation reports compatibility. | Lets callers choose the needed contract; two dialects and duplicated maintenance/diagnostics. |
| RX-D — Library-only, no core dialect | Provide string/search primitives and let packages select an engine. | Keeps language/runtime core small; weakens reproducible behavior across dependencies and encourages unsafe defaults. |

Independent semantic choices include leftmost-first versus leftmost-longest match, greedy/lazy/possessive behavior, capture results under repeated groups, Unicode versus ASCII shorthand classes, normalization policy, and whether match offsets are bytes, code units, scalars, or the string API's index type.

## 4. Discriminating experiments

1. Run standard adversarial patterns such as `(a+)+$` and `^(a|aa)+$` against near-miss inputs whose length grows geometrically. Measure steps/time and memory; verify that advertised bounds hold for search, captures, iteration, and replacement.
2. Vary both pattern size and input size; test nested alternation, counted repetition limits, huge capture counts, empty matches, zero-width loops, and repeated iterator calls.
3. Test look-around and backreferences against each dialect. For bounded engines, verify compile-time rejection and actionable diagnostics; for rich engines, exercise timeout/fuel exhaustion and ensure the host regains control.
4. Compare leftmost-first and leftmost-longest results for overlapping alternatives; record capture-group values and replacement output, not just Boolean match success.
5. Test Unicode classes, case folding, word boundaries, grapheme sequences, invalid UTF-8/byte inputs where supported, and offsets returned for non-ASCII prefixes. Pin Unicode/ICU data versions where they affect results.
6. Test cancellation, deadline expiry, task/process limits, compilation cache keys, and whether changing engine/version/dialect changes semantic artifact identity.

## 5. Current result

Regex is both a text semantics surface and a resource-consumption surface. Rust's common crate and Go's standard library constrain dialects to support bounded automata behavior; .NET demonstrates a dual-engine compromise; Foundation offers an ICU-compatible Unicode API without the cited same complexity guarantee. Unicode support alone does not establish a runtime bound. No LLMLang engine or dialect is selected; matching priority, Unicode version, compilation bounds, timeout semantics, and capture compatibility require explicit comparison.
