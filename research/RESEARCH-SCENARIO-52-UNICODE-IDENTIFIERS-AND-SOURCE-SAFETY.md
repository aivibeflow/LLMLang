# Research Scenario 52 — Unicode Identifiers and Source Safety

**Status:** Evidence-linked prior-art comparison; no LLMLang identifier repertoire or security profile selected  
**Research area:** RT-03 lexical semantics, RT-16 source integrity/tooling, RT-19 diagnostics  
**Updated:** 2026-11-19

## 1. Question and scope

Which characters may appear in identifiers, how are equivalent spellings compared, how does Unicode versioning affect language compatibility, and how should tools expose deceptive identifiers? These are distinct choices:

1. Character repertoire and start/continuation classes.
2. Normalization form and equality semantics.
3. Unicode database version and upgrade policy.
4. Case sensitivity and keyword escaping.
5. Script mixing, confusable detection, and bidi/format controls.
6. Compiler rejection versus linter/editor warning versus repository policy.
7. Source rendering, diffs, diagnostics, mangling, and external symbol constraints.

This report compares official Rust, Go, Swift, and Python references and Unicode UAX #31 / UTS #39 / UTS #55. Security recommendations must be evaluated against actual developer populations and tooling, not assumed from a character whitelist.

## 2. Prior-art comparison

### Rust: XID profile, NFC identity, pinned Unicode version

Rust identifiers use the XID_Start/XID_Continue profile, with underscore added to the start class, and the reference pins the properties to a named Unicode version. Identifiers are NFC-normalized for comparison, so canonically equivalent spellings resolve to one name. Some external symbol, crate/module path, and ABI-facing contexts impose ASCII restrictions; raw identifiers provide a spelling for keywords.

This supports international names while specifying deterministic identifier identity and preserving compatibility at external boundaries. Toolchains must maintain normalization/version behavior and present canonical identity clearly when source spellings differ.

Source: [Rust Reference — Identifiers](https://doc.rust-lang.org/reference/identifiers.html).

### Go: simple letter/digit classes, no normalization rule in identifier definition

Go defines letters by Unicode categories Lu, Ll, Lt, Lm, and Lo; digits are Nd, and an identifier begins with a letter followed by letters or digits. The grammar does not define a normalization-equivalence rule comparable to Rust NFC. Export visibility also depends on the first character being an uppercase Unicode letter.

The rule is comparatively compact and internationalized, while canonically equivalent or confusable spellings can remain distinct names. Since case affects package visibility, Unicode category and case behavior are also API semantics.

Source: [Go specification — Identifiers and exported identifiers](https://go.dev/ref/spec#Identifiers).

### Swift: broad Unicode identifiers and escaped/raw names

Swift permits many Unicode letters and non-ASCII characters in identifiers, permits combining characters after the first position, and offers backtick-delimited raw identifiers for keywords and special spellings. Its lexical reference has explicit exclusions for separators and control-like characters in raw names. This is expressive for scientific and multilingual source, but puts more weight on precise tokenization, rendering, and code review tools.

Source: [Swift Language Reference — Lexical Structure](https://docs.swift.org/latest/documentation/the-swift-programming-language/lexicalstructure/).

### Python: UAX #31 profile with NFKC canonicalization

Python bases identifier syntax on UAX #31 and converts names to NFKC while parsing. Thus compatibility characters can normalize to ASCII or other ordinary identifier sequences. This normalizes more distinctions than NFC and has language-specific implications for keyword-like or compatibility glyph spellings.

NFKC can reduce some compatibility-form duplicates but also changes spelling identity in ways that editors, diagnostics, and source-to-symbol maps must expose. Normalization alone does not prevent homoglyph spoofing across scripts.

Source: [Python Language Reference — Identifiers](https://docs.python.org/3/reference/lexical_analysis.html#identifiers).

### Unicode security standards: profiles and diagnostics, not a universal ban

UAX #31 defines identifier classes and profiles; its XID properties are designed to support normalization-aware identifier syntax and stable handling. UTS #39 defines restriction levels and mechanisms for mixed-script/confusable detection. UTS #55 cautions that mixed-script detection should not be naively applied as a blanket source-code rule: technical names legitimately mix scripts, and single-script confusables can still spoof familiar names.

These standards provide mechanisms for language and tool designers, not a one-size-fits-all compiler policy. A layered approach can keep valid source semantics separate from repository/editor security diagnostics.

Sources: [Unicode UAX #31 — Identifiers and Syntax](https://www.unicode.org/reports/tr31/), [Unicode UTS #39 — Security Mechanisms](https://www.unicode.org/reports/tr39/), [Unicode UTS #55 — Source Code Handling](https://www.unicode.org/reports/tr55/).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Python |
|---|---|---|---|---|
| Character rule | XID_Start / XID_Continue profile | Unicode letter categories plus Nd | Broad Unicode lexical classes | UAX #31-derived profile |
| Normalization identity | NFC | No canonical normalization specified by identifier grammar | Unicode lexical handling; define/version in language implementation | NFKC at parse time |
| Unicode version | Reference pins a version | Language/spec Unicode categories; version compatibility needs explicit attention | Versioned toolchain docs/implementation | Python release documents UCD profile/version |
| Keyword escape | `r#name` raw identifier | None in ordinary grammar | Backticks | Keywords plus soft keywords (grammar context) |
| Export interaction | Separate visibility controls | Uppercase first Unicode letter exports | Access modifiers | Module namespace/import rules |
| Security implication | Canonical equivalence coalesces NFC forms; homoglyphs remain | Visually similar identifiers can remain distinct; case affects export | Broad repertoire raises rendering/review burden | NFKC folds compatibility distinctions; homoglyphs remain |

## 4. Discriminating fixtures

1. Test ASCII, Greek/Cyrillic/Latin, ideographs, combining marks, emoji/symbols, private-use, join controls, bidi controls, and invalid scalar sequences against each candidate profile.
2. Test composed/decomposed equivalents under NFC and compatibility forms under NFKC; record token spelling, resolved identity, diagnostics, symbol mangling, and serialized interface names.
3. Test mixed-script and same-script confusables, including identifiers that visually mimic common built-ins or imported APIs; separate compiler result from lint/editor warning.
4. Test additions of characters introduced in a newer Unicode release against the same language version and source package; ensure old compiler and new compiler agree on source validity or fail with a clear version error.
5. Test case/normalization effects on exported names, module paths, filenames, generated identifiers, external linkage, and package archives across case-sensitive and case-insensitive filesystems.
6. Render source in terminal, editor, review diff, diagnostic spans, hover UI, and canonical AST output; confirm invisible/control characters and canonicalized spellings are visible to reviewers.
7. Fuzz normalization boundaries and source-map offset handling where normalization changes code-point count or representation.

Every fixture should report original source bytes, decoded scalar sequence, token spelling, canonical identifier key, Unicode version, security warning class, and public symbol/interface encoding.

## 5. Cross-area implications and open hypotheses

- Unicode property sets evolve. A language version should bind to a specified Unicode data version or have an explicit rule for new characters, otherwise compiler versions can disagree on tokenization and identifier validity.
- NFC and NFKC are semantic identity choices. NFC merges canonical equivalents; NFKC also folds compatibility distinctions. Either needs a documented policy for source maps, diagnostics, interface serialization, and external linkage.
- Normalization does not address visual confusables. UTS #39 restriction/confusable mechanisms are better treated as security diagnostics or configurable repository policy unless evidence supports compiler rejection.
- A strict ASCII-only profile simplifies source review, hashing, ABI, and cross-tool support, but limits native-language names and creates transliteration burden. Unicode identifiers offer inclusivity and domain notation but require mature tooling.
- Identifier equality, display spelling, and ABI/mangled spelling should be separate fields in compiler/tool APIs. Canonical equality must not erase the spelling needed to review or faithfully edit source.
- Security diagnostics need context: a mixed-script scientific name can be legitimate, while an identifier confusable with a standard-library security primitive is higher risk. Warnings should explain the exact confusable pair and avoid pretending they prove malicious intent.
- Source systems must preserve raw bytes/encoding policy and decoded scalar coordinates so parser spans, diagnostics, formatters, and semantic graph links agree.

No LLMLang Unicode repertoire, normalization form, Unicode versioning rule, keyword escaping syntax, or confusable-warning policy is selected.

## 6. Next research and falsifiers

Build a lexer corpus across pinned compiler versions for ASCII, UAX #31 XID, NFC, and NFKC candidate profiles. Add UTS #39 restriction-level/confusable analysis as an advisory channel, then conduct blind review tasks with developers using multiple scripts. Measure acceptance of legitimate names, spoof detection, false-positive burden, editor/diff readability, build reproducibility, and API/mangling stability. Include representative environments with different keyboards and scripts; do not infer usability from English-only review.

ASCII-only is weakened if it materially harms source expressiveness or forces pervasive transliteration. Broad Unicode is weakened if common tools fail to render or safely review names, or if compatibility/version changes cause divergent builds. Normalization is weakened if the chosen form causes surprising collisions or makes source changes hard to review. Any security profile is weakened if spoofing examples evade it or legitimate multilingual code is routinely rejected.

## 7. Sources and temporal limits

Official language references and Unicode standards were consulted 2026-11-19. Rust, Swift, Python, UAX #31, UTS #39, and UTS #55 are version-sensitive. Record exact language/toolchain and Unicode database versions with every executable result.
