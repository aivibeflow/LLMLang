# Research Scenario 133 — Generated Rust for Owned Results

**Status** — Bounded source-to-target conformance on Linux x86-64

**Research areas** — RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI · RT-21 bootstrap

**Updated** — 2026-11-20

## Question

Can generated Rust preserve the observations that distinguish transfer timing and caller recovery in COR-13? The experiment uses the proposed Rust output path and the two caller policies from Scenario 132. A mismatch in any recorded field fails the comparison. [ADR-016](../../../docs/adr/016-compiler-bootstrap.md) · [Typed caller recovery](../../language-design/RT-04/RESEARCH-SCENARIO-132-TYPED-CALLER-RECOVERY.md)

## Translation and observations

The generator validates the fixed callee and caller match with the existing source checker. It emits the resolved indices for both role pairs, the chosen transfer timing, and the Rust match arms for the checked caller actions. A handwritten Rust runtime implements the fixed callee, explicit cleanup, and the role guard. The Rust handle moves into an explicit close operation. The retained state carries the usable handle, while the reconciliation state carries only its possible role footprint. The checker rejects a release in a reconciliation arm and rejects a modified callee outside the supported shape. [Generator](../../PROTOTYPES/RT-04-01/rt04_rust_owned_probe.py) · [Runtime](../../PROTOTYPES/RT-04-01/rt04_owned_probe.rs) · [Rejection checks](../../PROTOTYPES/RT-04-01/test_rt04_rust_owned_probe.py)

Each native execution is compared with the Python reference from Scenario 132. The fields cover the original result tag and obligations, ordered events, the domain-error flag, ordered cleanup diagnostics, second-call admission, outstanding role pairs, and obligations forwarded by the caller. The reference's earlier comparison with direct transitions gives a second check on the original forwarding and recovery fixtures. [Reference and prior comparison](../../PROTOTYPES/RT-04-01/test_rt04_shared_owned_handlers.py)

## Results

Each source and transfer order has 10,496 inputs. The corpus preserves the 10,368 rows per order from Scenario 132 and adds 128 rows in which all four resource arguments differ. This covers every equality partition of four arguments under the fixture's identity model, both domain outcomes, and all combinations of four dispositions at each of the three cleanup sites. The third source retargets the second destination from argument `d` to argument `a`, which is also the first source.

| Source | Starts with transfer before cleanup | Starts with transfer after cleanup |
|---|---:|---:|
| Forward all obligations | 1,856 | 2,576 |
| Release a usable handle on an error arm | 2,816 | 2,996 |
| Same recovery with the second destination aliased to the first source | 2,368 | 2,590 |

All 62,976 traces per optimization level match the reference across the six source and transfer configurations. Both `opt-level=0` and `opt-level=3` agree, for 125,952 native comparisons in total. The additional all-distinct rows increase admission equally for the two original caller policies. The retargeted fixture lowers admission because a prior reservation can conflict with the newly aliased destination, including when the raw arguments differ.

## Reproduction and scope

```sh
python -B research/PROTOTYPES/RT-04-01/rt04_rust_owned_probe.py --rustc /path/to/rustc
```

The runner requires Rust 1.85.1 and compiles the generated source with edition 2021 and warnings denied. The measured host was `x86_64-unknown-linux-gnu` with `rustc` commit `4eb161250e340c8f48f66e2b929ef4a5bed7c181`, LLVM 19.1.7, GCC driver 14.2.0, GNU ld 2.44, and Python 3.12.14. The probe uses the Rust standard library. The repository's Python suite checks the generator and source rejections. The command above runs the native conformance corpus separately.

The result establishes preservation for this fixture with an explicit carrier for obligations and explicit cleanup. Release dispositions and resource identities are supplied by the corpus. General lowering, live FFI and concurrency, other host targets, and the clean-machine bootstrap chain remain open. [Bootstrap acceptance criteria](../../../docs/adr/016-compiler-bootstrap.md#validation-required-before-acceptance)
