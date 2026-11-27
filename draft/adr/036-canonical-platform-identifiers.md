# ADR-036 — Define canonical platform identifiers

- **Status** — Proposed
- **Date** — 2026-11-27
- **Scope** — Values of `BINDINGS.platform` and their use in build-time selection
- **Related decisions** — [ADR-035](035-platform-specific-bindings.md)

## Context

The Toolchain selects platform-specific bindings by exact identifier. Rust,
Clang, and GCC can use different spellings for the same platform. A shared
LLMLang list lets package authors and build tools agree on the value stored
in `BINDINGS.platform`. The selected build profile supplies the compiler's
target spelling, SDK, and other toolchain options.

## Decision

Use `<architecture>-<os>` for a canonical platform identifier. Append an
environment suffix where the list distinguishes environments for the same
architecture and OS. For example, `aarch64-ios` identifies an iPhone device
and `aarch64-ios-simulator` identifies the ARM64 simulator.

The entire `BINDINGS.platform` value must match `[A-Za-z0-9_-]*`. The allowed
characters are ASCII letters, digits, underscores, and hyphens. A nonempty
value must match a listed identifier exactly and case-sensitively. The
empty string `""` denotes a platform-independent binding. For a given pinned
version and interface, the Toolchain selects the exact platform row first and
uses the empty row when the exact row is absent.

### Allowed platform identifiers

- `x86_64-linux`
- `aarch64-linux`
- `i686-linux`
- `x86_64-windows`
- `aarch64-windows`
- `aarch64-macos`
- `x86_64-macos`
- `aarch64-android`
- `armv7-android`
- `x86_64-android`
- `i686-android`
- `aarch64-ios`
- `aarch64-ios-simulator`
- `x86_64-ios-simulator`

## Alternatives and consequences

Compiler target triples can encode vendor and runtime choices directly.
Using them in package rows would couple binding keys to compiler-specific
names. Canonical identifiers give the Toolchain a shared key and require each
build profile to supply its compiler mapping. A listed identifier may be
stored as a binding value. Building for it also requires a Toolchain profile
that supports the target.

Adopting this decision updates the allowed characters and canonical examples
in ADR-035. The existing binding key and selection order continue to apply.

## Implementation validation

- Accept every listed identifier and the empty binding value. Reject unknown
  names, case variants, and strings containing characters outside the grammar.
- Resolve `i686-linux` as the canonical identifier for 32-bit Linux x86.
- Check that ARM64 iPhone and ARM64 iOS Simulator builds select their own
  exact rows when both appear in the same version.
