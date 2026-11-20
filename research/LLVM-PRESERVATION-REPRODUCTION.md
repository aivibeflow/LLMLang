# LLVM Preservation Reproduction Protocol

**Status:** freshly reproduced by llvm-preservation job 44773422416; both probes passed and artifact 14647744441 preserves the manifest and outputs.

## Scope

Reproduce the two bounded native experiments in Scenarios 96A and 96B:

- integer arithmetic, checked errors, ordered effects, and result-slot preservation at LLVM O0/O3;
- logical byte-view bounds and origin checks, including verifier-accepted negative controls.

These are narrow source-to-LLVM experiments, not a complete frontend/backend proof, a selected LLMLang memory model, or a decision to make LLVM the primary backend.

## Pinned environment

The llvm-preservation job in .github/workflows/rt04-native-reproduction.yml runs in Debian Trixie and requires:

| Component | Required identity |
|---|---|
| Python | 3.12.14 |
| Debian package | llvm-19 1:19.1.7-3+b1 |
| LLVM tools | opt-19 and llc-19, version 19.1.7 |
| Tool package archive | SHA-256 0b1b7263f4f45e261099240fdbf00fc14b42b88410fd829e041bf83ea45866cb |
| C compiler | GCC 14.2.0 |
| Linker | GNU ld 2.44 |

The archive SHA-256 is checked before the probes run. The package version and executable versions are independently checked by the runner. The workflow records Python 3.12.14, platform/libc, compiler, linker, tool versions, package archive hash, repository commit, commands, exit codes, and stdout/stderr. The successful run used glibc 2.41 and libffi 3.4.8, matching the report.

## Commands

The runner invokes the exact report commands with explicit tools:

- llvm_integer_probe.py --opt /usr/bin/opt-19 --llc /usr/bin/llc-19 --cc /usr/bin/gcc-14
- llvm_view_probe.py --opt /usr/bin/opt-19 --llc /usr/bin/llc-19 --cc /usr/bin/gcc-14

Each command has a 900-second timeout. The runner preserves separate logs and a machine-readable summary.json as a 30-day Actions artifact.

## Historical expected results

Scenario 96A reports 20,978 comparisons at each of O0 and O3, 41,956 total, with zero mismatches. Its deliberately mutated overflow branch remains verifier-accepted but differs from the source reference on the signed maximum witness.

Scenario 96B reports 9,800 comparisons at each of O0 and O3, 19,600 total, with zero mismatches. Two verifier-accepted controls violate logical view bounds or origin identity while remaining within the physical allocation.

The workflow does not silently rewrite these expected values. A mismatch is a failed reproduction and must be recorded as such.

## Provenance boundary

The report's baseline commit is the pre-experiment source revision, not the commit that introduced the probe. Scenario 96A records experiment source commit a80d94e795d8d2b613d01c09687c181df592c7f5; Scenario 96B records 2a9b6e5072efc542e823c529cf3cdee838f9ad36. The runner executes the checked-out current probe source and records the actual repository commit. This is a fresh reproduction of the recorded fixtures/toolchain, not a claim that the old source commit is checked out.

The historical reports do not claim Required CI executes these native experiments. The dedicated workflow job remains separate from Required CI and must pass before a fresh reproduction is recorded.

## Remaining work

- Preserve artifact 14647744441 and workflow run 44773422416 in the RT-00 audit.
- Keep the tested subset/target limits explicit; the successful run is a fresh reproduction of the fixed fixtures, not a whole-domain proof.
- Keep the tested subset/target limits explicit; whole-domain proof, other targets, constant folding, general provenance, floating point, atomics, and a complete source-to-LLVM pipeline remain open.
