# Research Scenario 46 — Strings, Unicode, and Indexing

**Status:** Evidence-linked prior-art comparison; no LLMLang string model selected  
**Research area:** RT-03 text value semantics, RT-04 string types, RT-09 storage/runtime, RT-18 Unicode versioning  
**Updated:** 2026-11-19

## 1. Question and scope

What does a string value guarantee about encoding, and what does an index or iteration step mean: byte, code unit, Unicode scalar value, extended grapheme cluster, or a domain-specific text segment?

Keep these concerns distinct:

1. Binary data versus text: arbitrary bytes versus validated text encoding.
2. Storage encoding: UTF-8, UTF-16, UTF-32, or an abstract encoding-independent value.
3. Iteration/index units: bytes, code units, scalar values, grapheme clusters.
4. Equality/ordering: byte equality, scalar sequence equality, canonical equivalence, locale-aware collation.
5. Normalization: whether text is preserved as supplied or normalized at specified boundaries.
6. Versioning: Unicode data and segmentation algorithms can change across releases.
7. Invalid input: reject, preserve raw bytes, replace invalid sequences, or expose a decoding result.

This report compares Rust, Go, and Swift string APIs and Unicode Consortium specifications. It does not specify collation, locale APIs, regular expressions, terminal width, identifier confusables, or a full grapheme-breaking implementation.

## 2. Prior-art comparison

### Rust: valid UTF-8 string type; explicit byte/scalar views

Rust str and String guarantee valid UTF-8. Byte access and slicing use byte offsets, with slices required to begin and end on UTF-8 boundaries; indexing by an integer as a character is not provided. The standard library exposes separate byte and char iteration, where char represents a Unicode scalar value. Grapheme-cluster segmentation is not part of the standard String indexing API.

This keeps the core representation compact and makes binary decoding an explicit conversion, but leaves user-perceived-character segmentation to an additional library. It also makes the complexity of byte and scalar traversal visible rather than implying constant-time character indexing.

Sources: [Rust Book — Strings and UTF-8](https://doc.rust-lang.org/book/ch08-02-strings.html), [Rust str reference](https://doc.rust-lang.org/std/primitive.str.html), [Rust String API](https://doc.rust-lang.org/std/string/struct.String.html).

### Go: strings are byte sequences; UTF-8 is a convention for text

The Go specification defines a string as a possibly empty sequence of bytes. String literals are UTF-8 encoded source text, but arbitrary runtime strings need not contain valid UTF-8. Indexing accesses bytes; ranging decodes UTF-8 code points and yields the replacement RuneError for invalid encodings. A rune is an alias for int32 and commonly represents a Unicode code point, not necessarily a user-perceived character.

This makes strings useful for byte-oriented protocols and avoids imposing validation on every value. It places responsibility on APIs to distinguish text from arbitrary byte sequences and on callers to decide what malformed UTF-8 means.

Source: [Go specification — String types and range](https://go.dev/ref/spec#String_types), [Go blog — Strings, bytes, runes and characters](https://go.dev/blog/strings).

### Swift: Character iteration uses extended grapheme clusters

Swift String is Unicode-aware, and each Character represents an extended grapheme cluster: one or more Unicode scalar values. String indexing follows Character boundaries, not integer offsets, bytes, or scalars. String and Character equality use canonical equivalence; the language guide distinguishes these comparisons from locale-sensitive collation.

This makes common text iteration line up more closely with user-perceived characters, but a Character is a segmentation result rather than one scalar or fixed-width unit. Index traversal and storage assumptions must account for variable-width text and Unicode segmentation behavior.

Source: [Swift Language Guide — Strings and Characters](https://docs.swift.org/swift-book/LanguageGuide/StringsAndCharacters.html).

### Unicode specifications: grapheme boundaries and normalization are versioned policies

Unicode Standard Annex #29 defines default algorithms for extended grapheme clusters, words, and sentences. The annex describes guidelines and default boundaries, not a universal perfect mapping to human-perceived characters. The current version consulted here is Unicode 18.0.0, UAX #29 revision 49.

Unicode Standard Annex #15 defines NFC/NFD canonical and NFKC/NFKD compatibility normalization. Normalization can make equivalent text have a common binary representation, but compatibility normalization can change distinctions that applications may care about. Importantly, normalized strings are not generally closed under concatenation: concatenating two NFC strings can produce text that needs re-normalization.

Sources: [Unicode UAX #29 — Text Segmentation](https://www.unicode.org/reports/tr29/), [Unicode UAX #15 — Normalization Forms](https://www.unicode.org/reports/tr15/).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift |
|---|---|---|---|
| Runtime string invariant | Valid UTF-8 | Arbitrary byte sequence | Unicode text with Character abstraction |
| Integer indexing | Not supported as character indexing; byte slicing at UTF-8 boundaries | Byte offset | String.Index at Character boundary; no general integer character offset |
| Scalar iteration | Explicit char iterator | range decodes UTF-8 into rune/code point values | Unicode.Scalar view |
| Grapheme iteration | External segmentation library | Not supplied by core string iteration | Character iteration uses extended grapheme clusters |
| Invalid UTF-8 | Cannot inhabit str/String without validation or unsafe construction | Can be stored; range substitutes RuneError for invalid encoding | Text APIs expose Unicode-aware behavior; raw bytes require decoding/bridging decisions |
| Equality | String byte content equality for valid UTF-8 | Byte sequence equality | Canonical equivalence for String/Character equality |
| Normalization default | No automatic normalization guarantee | No automatic normalization guarantee | Canonical-equivalence comparisons; do not infer a stored normalized form |
| Text segmentation version | Library/data dependency if grapheme segmentation is needed | External package/data dependency | Runtime/library Unicode implementation dependency |

The comparison distinguishes storage invariants from text APIs. “Character” is intentionally avoided as an unqualified unit because the languages use the term differently.

## 4. Discriminating fixture

Use a corpus containing:

- ASCII text, multi-byte UTF-8 scalars, supplementary-plane scalars, combining marks, Hangul jamo sequences, regional-indicator flags, emoji modifiers, and zero-width-joiner emoji sequences.
- Canonically equivalent composed/decomposed forms such as precomposed é versus e plus combining acute.
- Invalid UTF-8 byte sequences, embedded zero bytes, and protocol payloads that are not text.
- Concatenation of separately NFC-normalized strings whose boundary changes normalization.
- A source file and identifier corpus with non-ASCII characters (identifier security is a separate follow-up).

Record byte length, code-unit length, scalar count, grapheme count, equality result, normalization form before/after concatenation, slicing/index boundaries, invalid-input behavior, and runtime/data version. Include complexity measurements for repeated indexed access versus sequential iteration. Verify round trips through filesystem and network encodings separately from in-memory string behavior.

## 5. Cross-area implications and open hypotheses

- One general String type cannot simultaneously make arbitrary byte storage, valid text, scalar iteration, and user-perceived-character indexing the cheapest/default operation. A separate ByteString/Bytes and validated Text abstraction is a candidate to evaluate, not a selected design.
- Grapheme-based Character indexing improves common UI operations but ties results to segmentation rules and may not match linguistic notions of a character.
- Normalizing all strings at construction simplifies some equality/hash boundaries but changes input representation and does not remain invariant under naive concatenation.
- Canonical-equivalence equality is not locale-aware comparison and does not solve collation, search, spoofing, or identifier security.
- String content hashes must state whether they commit to raw bytes or normalized/canonical text. Unicode version and normalization policy can become hash-relevant inputs.
- Rust's UTF-8 validity invariant and Go's byte-sequence model are distinct safety/interoperability trade-offs; neither alone decides the right protocol API.

## 6. Next research and falsifiers

Implement the corpus in candidate Text and Bytes APIs. Add property checks for valid UTF-8 slicing, round trips, canonical equality, normalization boundaries, and Unicode version pinning. Measure index/iteration complexity and confirm that external protocol parsing does not accidentally decode or normalize payloads. Add identifier-security cases separately using Unicode identifier and confusable guidance.

The grapheme-first API is weakened if routine code needs byte offsets for protocols or if segmentation/indexing costs are unexpected. The byte-string-only model is weakened if text callers routinely mishandle malformed encoding or repeat conversion logic. Eager normalization is weakened if applications need byte-for-byte preservation or concatenation invariants become costly. No model is adequate unless its equality, indexing unit, and Unicode version are explicit at API and hash boundaries.

No LLMLang String type, indexing rule, normalization policy, or Unicode version is selected.

## 7. Sources and temporal limits

Official language documentation and Unicode standards were consulted 2026-11-19. UAX #29 is Unicode 18.0.0 revision 49; APIs that expose segmentation behavior should pin or report their Unicode data version. Language docs are rolling and runtime implementation details vary by release. This report is a prior-art comparison, not a performance or Unicode conformance test.
