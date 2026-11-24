# Research Scenario 38 — Effects, Capabilities, and Authority

**Status:** Evidence-linked comparison; no LLMLang authority or effect model selected
**Research area:** RT-04 types, effects, ownership, capabilities, and RT-16 security boundaries
**Updated:** 2026-11-19

## 1. Question

What does an effect declaration guarantee, what does a capability grant, and which part of that contract must be enforced by the runtime or trusted boundary?

The word *capability* is used for more than one thing. In an effect-handler language, it can mean that an operation has a handler available in the current dynamic context. In object-capability systems, it means possession of a reference that carries authority. In security protocols, it can mean an unforgeable token that proves a permission. These meanings can be composed, but they are not interchangeable.

This report distinguishes four fields:

| Field | Question it answers | Typical evidence |
|---|---|---|
| **Effect bound** | Which kinds of interaction may this computation perform, including through callees? | Static effect row, effect signature, verified transitive summary |
| **Authority capability** | Which resource/action scope is this principal allowed to attempt? | Unforgeable handle/token plus runtime policy, or a proof checked at a trusted boundary |
| **Runtime availability** | Which host operations were actually supplied to this program instance? | Import/linker table, sandbox profile, capability environment |
| **Observed behavior** | Which operation occurred, with what input, result, and order? | Ordered event trace or concurrency-aware trace witness |

None subsumes all the others. A function may have a `filesystem.read` effect bound and never read; a process may hold a directory handle but never use it; a host may provide an import that the program never invokes; and an invoked read may fail.

## 2. Prior-art comparison

### Koka: handler availability as a contextual capability

Koka describes an effect as an abstract set of operations whose implementation can be dynamically bound by a handler. Its manual says a function with a `raise` effect needs that effect handled in its evaluation context and calls that a `raise` “capability.” Koka's row-polymorphic functions can also propagate the outstanding effect in their own result row; the handler need not be installed at every intermediate call. For a closed computation that does not expose the effect further, a handler must supply its interpretation, subject to the language's effect typing and trusted boundaries.

This is not automatically a security credential. The row/handler relation chooses an interpretation for an operation; it does not by itself identify an authenticated principal, constrain a filesystem path, establish that the handler enforces least authority, or prevent unsafe/foreign code from bypassing the contract. A handler may implement an authorization check, but that policy is supplied by the handler and its trust boundary.

Source: [Koka effect handlers and the contextual “capability” terminology](https://koka-lang.github.io/koka/doc/book.html#handling).

### Rust `cap-std`: object handles and explicit ambient escape

`cap_std::fs::Dir` is a reference to an open directory. Its `open`, `create`, and related methods operate on paths relative to that handle. The API also has explicit `open_ambient_dir` and `open_parent_dir` methods that take `AmbientAuthority`; their documentation warns that these operations use process authority and are not sandboxed to the handle's subtree.

This makes authority visible in the value/API boundary: a callee given only a `Dir` can operate relative to that directory, subject to operating-system and library guarantees. It does not provide a transitive effect summary by itself. A function that receives `Dir` may or may not read, and the type `Dir` does not say whether the current call actually did so. Ambient escapes also show why a capability discipline must specify FFI, raw descriptors, and unsafe APIs.

Source: [`cap_std::fs::Dir`](https://docs.rs/cap-std/latest/cap_std/fs/struct.Dir.html), including its relative operations and ambient-authority escape methods.

### F*: cryptographic tokens as proof of authority

An official F* tutorial exercise defines a cryptographic capability for file access. A trusted ACL/MAC layer issues a token only when `canRead(file)` holds; redeeming the token verifies the MAC and returns a value whose refinement states `canRead(file)`. The example explicitly assumes MAC unforgeability for its security argument. The effect (`ML`) and the authority predicate/token are represented separately.

This illustrates a stronger, proof-oriented capability claim than an effect-row label: possession/redeeming of a token is connected to an authorization proposition. The result still depends on assumptions about the trusted issuer, key handling, MAC implementation/security, file-name encoding, and the boundary through which reads occur. The example is in F*'s older official tutorial; treat it as a design case study and recheck syntax/library details against a selected F* release.

Source: [F* tutorial: Cryptographic Capabilities for Accessing Files](https://fstar-lang.org/tutorial/old/tutorial.html#cryptographic-capabilities-for-accessing-files).

### Wasmtime: host imports as an instance-level authority boundary

Wasmtime's `Linker` resolves each module import against host-defined entries. Instantiation fails if an import is absent or has an incompatible type. This allows the embedder to decide which host functions are available to the guest instance. It is a runtime authority boundary, but the import's type alone does not guarantee the host implementation is least-authority: a host function can itself call ambient APIs or expose broad authority.

Source: [Wasmtime `Linker::instantiate`](https://docs.wasmtime.dev/api/wasmtime/struct.Linker.html).

## 3. Minimal operation contract

Consider a function that reads a file through a directory handle:

```text
read_config(dir: Dir, path: RelativePath)
  requires effect filesystem.read
  requires capability DirRead(dir, path)
  returns Result<Bytes, FsError>
```

The declaration separates **what may happen** from **what authority is needed**. A runtime trace records **what did happen**:

```text
filesystem.read(path, bytes-read, success-or-error)
```

This distinction yields discriminating cases:

| Effect bound | Capability | Execution | Expected evidence to distinguish |
|---|---|---|---|
| Read permitted | In scope | Function does not read | Static allowance present; no read event |
| Read permitted | Missing | Known call requires it | Static rejection where possible, otherwise explicit authorization failure before the OS action |
| Read permitted | In scope | Read succeeds | Read event with normalized path, bytes/outcome, and trace position |
| Read permitted | In scope | OS returns error/partial read | Same authority grant, different operation outcome and possibly a partial-effect trace |
| Read omitted | In scope | Implementation attempts read | Type/effect violation or failed trusted-boundary check; capability alone must not imply the effect declaration was satisfied |
| Read permitted | Broad ambient authority | Implementation uses raw/global API | Must remain visible as an ambient escape or unknown authority boundary |

The failure/partial-read case matters for POSIX I/O: authority only permits an attempt; it does not promise success, atomicity, or a particular byte count.

## 4. Cross-area constraints and discriminators

- A static effect row is a behavioral upper bound or interface, not proof that the runtime granted the corresponding authority.
- A capability is permission to attempt an action within a scope; it does not prove the action occurred, succeeded, or had no other effects.
- A runtime import table shows available host entry points, not which of them are invoked or what their implementations do.
- Handler presence can provide a typed interpreter and may enforce policy, but security depends on the handler's semantics and trusted deployment boundary.
- Passing a capability across a call must be explicit enough to audit delegation and attenuation. Passing an effect label alone does not transport authority.
- Dynamic dispatch, FFI, raw file descriptors, ambient process APIs, and host callbacks need effect summaries and capability provenance; unknown boundaries cannot be treated as safe by declaration alone.
- Evidence/caches should commit separately to effect contract, authority policy/capability scope, runtime import configuration, and observed trace where each affects the claim.

Discriminating follow-up probes should compare a narrowed directory handle with an ambient escape, a capability that is passed but never used, an allowed effect without authority, a capability used through a transitive helper, a revoked/stale token, and a host import whose implementation exceeds its advertised scope. Record static effects, required/granted capabilities, runtime imports, external events, result/error, and trust assumptions separately.

The candidate vector is weakened if capability possession is treated as evidence of effect behavior, effect permission is treated as authorization, or the runtime can perform operations absent from the declared contract without a visible unsafe/unknown boundary. A vector with only dynamic capability checks is weakened if it cannot statically summarize transitive effects for API review, impact analysis, and evidence reuse. This evidence selects no LLMLang mechanism.

## 5. Current conclusion

Koka's use of “capability” for a handler available in dynamic context is distinct from the scoped `Dir` object in `cap-std` and the cryptographic permission token in F*. Wasmtime's import binding supplies yet another enforcement point at instantiation. These sources support modeling effect bounds, authority, runtime availability, and observed behavior as related but separate evidence. No LLMLang feature is selected.
