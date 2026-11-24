# Research Scenario 90 — Runtime Hashing, Determinism, and Persistent Identity

**Status:** Evidence-linked prior-art comparison; no LLMLang hashing or iteration policy selected
**Research area:** RT-03 equality/collections, RT-05 semantic identity, RT-06 dependency indexes, RT-18 reproducibility
**Updated:** 2026-11-19

## 1. Question and relation to prior work

Which guarantees belong to a hash function used inside a runtime collection, which belong to iteration order, and which belong to a stable digest persisted in a cache or semantic repository?

[Scenario 63](../../language-design/RT-03/RESEARCH-SCENARIO-63-EQUALITY-IDENTITY-AND-HASHING.md) compares equality, identity, and hash-key laws, and explicitly leaves persistence across runs open. This scenario isolates stability, randomization, iteration, and persistent identity. A map's hash function is not automatically an artifact-address algorithm, and a stable digest does not specify collection iteration order.

## 2. Prior-art comparison

### Rust: key-consistency contract, no cross-platform/compiler stability promise

Rust's Hash trait describes how a value feeds data to a Hasher. Equal values must produce the same hash input sequence, and implementations are expected to preserve prefix-free structure. The standard documentation cautions that feed sequences may vary across platforms because of endianness and type size, and that standard library types' sequences should not be assumed stable across compiler versions. Portable serialization should not persist those hashes unless the relevant implementation offers additional guarantees.

This makes Hash useful as a collection contract while deliberately leaving portable content identity to a separate, explicitly guaranteed format.

Source: [Rust std::hash::Hash](https://doc.rust-lang.org/stable/std/hash/trait.Hash.html).

### Swift: per-execution Hasher for Set and Dictionary

Swift documents Hasher as the universal hash function for Set and Dictionary. Feeding the same byte sequence yields the same result within a single program execution, but the algorithm uses a seed and the documentation says not to save or reuse results across executions.

The public contract directly separates in-process collection behavior from persistent identity.

Source: [Swift Hasher](https://docs.swift.org/latest/documentation/swift/hasher/).

### Python: salted str/bytes hashes and opt-in fixed seed

Python salts built-in string and byte hashes with an unpredictable random value by default. Values remain constant within one process but are not predictable across program invocations. The documentation identifies protection against adversarial hash-table collision attacks as the purpose. PYTHONHASHSEED can provide a fixed seed for controlled environments, which changes the default protection/reproducibility balance.

This is a runtime table defense and operational reproducibility control, not a portable identity format.

Sources: [Python data model — hash values](https://docs.python.org/3/reference/datamodel.html#object.__hash__), [Python command-line/environment — PYTHONHASHSEED](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED).

### Go: map iteration order is deliberately unspecified

The Go specification does not promise a map iteration order and explicitly says it need not be the same from one iteration to the next. That is an observable collection contract independent of any promise about the exact hash algorithm or numeric hash values.

Therefore, applications requiring deterministic serialization or diagnostics must impose a separate ordering rule rather than rely on map traversal.

Source: [Go specification — Range clause](https://go.dev/ref/spec#For_statements).

### NIST secure message digests: a different contract again

NIST FIPS 180-4 specifies secure hash algorithms that produce message digests for security uses. Such a digest is a candidate building block for integrity or content addressing, but does not itself define canonical serialization, schema/version domains, semantic equivalence, or a collision-free identity model.

Source: [NIST FIPS 180-4 — Secure Hash Standard](https://csrc.nist.gov/pubs/fips/180-4/final).

## 3. Separate the contracts

| Contract | Typical use | Required decisions |
|---|---|---|
| Runtime key hash | Route a key to a hash table bucket | Equality/hash consistency, key mutation rules, seed/keying, collision behavior, key-width/platform limits |
| Collection iteration | Visit map/set entries | Ordered, insertion ordered, canonical-key ordered, or unspecified; mutation during iteration |
| Stable non-cryptographic fingerprint | Memoization or local build cache | Canonical input encoding, version scope, collision handling, target/compiler coverage |
| Cryptographic digest | Content-addressed store or integrity check | Algorithm/version, canonical bytes, domain separation, truncation, migration, trust/authentication boundary |

A deterministic hash-table function does not guarantee deterministic iteration: bucket capacity, insertion history, resizing, and traversal strategy can still change order. Conversely, a process-randomized table hash can coexist with deterministic output by sorting entries using an independent canonical key before serialization.

A secure digest is not a substitute for semantic canonicalization. If two source spellings encode the same LLMLang value or contract, the canonicalization layer must decide whether they share a digest input. If two different artifact kinds have identical bytes, domain separation should prevent accidental cross-kind identity. These are representation/evidence rules, not ordinary Map semantics.

## 4. Candidate policies

- **H-A Process-randomized runtime hashing, unspecified iteration.** Better resistance to collision flooding; deterministic tools sort keys when output order matters.
- **H-B Deterministic runtime hashing and specified iteration.** Easier replay and snapshots, but requires a deliberate security analysis for attacker-controlled keys and stable order costs.
- **H-C Per-collection hasher policy.** A secure default for ordinary maps and an explicit deterministic/ordered collection for reproducible traversal.
- **H-D Distinct APIs by purpose.** Keep ordinary Hash/Map contracts process-local; expose a separately versioned StableDigest/CanonicalEncode contract for persistent identity; ordered maps remain separate.

These directions can combine. Scenario63's equality law still applies: equal keys must hash consistently within the selected runtime contract. Persistent identity must additionally define canonical serialization and versioning. No candidate is selected.

## 5. Discriminating experiments

No LLMLang implementation or benchmarks have been run. A future matched experiment should:

1. Check equal keys feed equal hash data, including custom equality, strings with normalization, numeric edge values, and nested products/sums.
2. Record runtime hash outputs across repeated processes, runtime seeds, architectures, compiler versions, and collection growth histories.
3. Measure collision-heavy attacker-controlled keys under randomized and deterministic hashers, with bounded runtime/memory observations.
4. Serialize the same map after different insertion orders and process seeds; compare unspecified traversal, insertion order, and canonical sorted output.
5. Rebuild a content digest from canonical bytes across compiler/platform versions; change schema version, target profile, artifact kind, and field order independently.
6. Inject deliberate/truncated digest collisions and verify that the storage layer checks canonical content or handles collision buckets instead of assuming the digest is unique.
7. Test seed configuration in developer, CI, and production modes; ensure environment overrides cannot silently become part of a persisted identity contract.

Record equality result, raw encoding, hash algorithm/seed/version, iteration order, serialized bytes, digest domain, and collision-resolution path as separate evidence fields.

## 6. Open questions and limits

LLMLang still needs separate policies for adversarial map keys, default map iteration, stable build/cache keys, semantic artifact addresses, and cryptographic integrity. An environment variable that fixes a runtime seed can help diagnose nondeterministic tests, but should not define the persistent identity of a language artifact. A stable fingerprint may be useful for cache lookup without being a cryptographic authenticity proof.

The sources establish prior-art contracts, not the best LLMLang choice. FIPS 180-4 describes secure message-digest algorithms, but selecting one requires separate threat-model, canonical-encoding, migration, and performance work. No hash width, algorithm, seed policy, map order, or identity model is selected.

## 7. References

- [Rust std::hash::Hash](https://doc.rust-lang.org/stable/std/hash/trait.Hash.html)
- [Swift Hasher](https://docs.swift.org/latest/documentation/swift/hasher/)
- [Python data model — hash values](https://docs.python.org/3/reference/datamodel.html#object.__hash__)
- [Python command-line/environment — PYTHONHASHSEED](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED)
- [Go specification — Range clause](https://go.dev/ref/spec#For_statements)
- [NIST FIPS 180-4 — Secure Hash Standard](https://csrc.nist.gov/pubs/fips/180-4/final)
