# ADR-036 — Split binding targets into architecture and operating system

- **Status** — Accepted
- **Accepted** — 2026-11-27
- **Date** — 2026-11-27
- **Scope** — Binding keys, canonical build targets, and selection priority
- **Related decisions** — [ADR-035](035-platform-specific-bindings.md)

## Context

An implementation can depend on the operating system or the processor
architecture. For example, one implementation may use a Linux API available
on several architectures, while another may use x86-64 instructions across
several operating systems. A binding needs to express either constraint
independently. The Toolchain derives the target from the build request and
uses the build profile to map it to compiler options and an SDK.

## Decision

Replace the `platform` column in `BINDINGS` with required `arch` and `os`
columns. Each is a case-sensitive ASCII string that fully matches
`[A-Za-z0-9_-]*`. An empty string `""` matches every registered target value
for that column.

| Column | Logical type | Key and meaning |
| --- | --- | --- |
| `version_hash` | Hash | Primary key component and foreign key to `VERSIONS.version_hash`. |
| `interface_hash` | Hash | Primary key component and foreign key to `INTERFACES.interface_hash`. |
| `arch` | ASCII string | Primary key component. A canonical processor architecture or `""`. |
| `os` | ASCII string | Primary key component. A canonical OS target, including its execution environment where applicable, or `""`. |
| `impl_hash` | Hash | Foreign key to `FUNCTIONS.impl_hash`. Identifies the selected implementation. |

The primary key is `(version_hash, interface_hash, arch, os)`. Each key is
unique. Within a version, a qualified public name identifies one interface
revision across all its binding rows. The version's `binding_hash` covers
both target columns and the implementation hash of each row. The repository
profile defines the physical encoding.

### Allowed build targets

Every build target specifies a nonempty pair from this list. A binding with
both columns set must use a listed pair. A binding with one column set must
use a value from the corresponding column of the list.

| `arch` | `os` |
| --- | --- |
| `x86_64` | `linux` |
| `aarch64` | `linux` |
| `i686` | `linux` |
| `x86_64` | `windows` |
| `aarch64` | `windows` |
| `aarch64` | `macos` |
| `x86_64` | `macos` |
| `aarch64` | `android` |
| `armv7` | `android` |
| `x86_64` | `android` |
| `i686` | `android` |
| `aarch64` | `ios` |
| `aarch64` | `ios-simulator` |
| `x86_64` | `ios-simulator` |

The `os` value `ios` identifies an iPhone device target. The
`ios-simulator` value identifies the simulator's execution environment, which
has its own compiler target and SDK.

### Binding selection

For the pinned version and interface revision, a binding is eligible when
each of its target columns is empty or equals the corresponding build target
value. An explicit match takes precedence over an empty column. For a build
with `arch = "x86_64"` and `os = "linux"`, this gives the following order.

| Priority | Eligible pairs `(arch, os)` | Coverage |
| --- | --- | --- |
| 1 | `("x86_64", "linux")` | Exact architecture and OS |
| 2 | `("x86_64", "")` or `("", "linux")` | One explicit constraint |
| 3 | `("", "")` | All targets |

If both partial matches are eligible and no exact row exists, the build
reports an ambiguous binding with both keys. An exact row resolves this
overlap. If no row is eligible, the build reports the missing implementation
with the interface, version, architecture, and OS. A selected row with an
invalid implementation fails validation at its priority.

A provider must match the interface signature and refine the public contract
on every supported target covered by its row. The call verification context
records the build target and the selected binding, including its exact
implementation hash. Direct calls continue to pin platform-independent
implementations.

## Alternatives and consequences

A single identifier can represent each exact target. Independent columns
also let a package share one implementation across architectures or OS
targets. Giving one column precedence over the other would resolve overlapping
partial rows automatically. Reporting the overlap instead lets the package
author choose the implementation by supplying an exact row.

## Implementation validation

- Accept all listed target pairs and reject pairs absent from the list.
- Verify that an exact row wins over both partial rows and the universal row.
- Verify that either partial row wins over the universal row when it is the
  only matching partial row. Report ambiguity when both partial rows match
  and there is no exact row.
- Verify that an ARM64 iPhone and an ARM64 iOS Simulator select their own exact
  rows when both appear in one version.
