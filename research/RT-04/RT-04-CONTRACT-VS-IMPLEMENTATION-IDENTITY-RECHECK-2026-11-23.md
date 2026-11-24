# RT-04/RT-05: Contract identity versus implementation identity recheck

**Date:** 2026-11-23  
**Baseline:** `9135dfbe7724e12f2bbd664b53d860ec2f428d8b` (`main`)  
**Related plan items:** §1.3 contracts and compatible implementations; §1.5 semantic identity prior art; §3.4 cache action identity.

## Discriminating question

Can two different implementations produce observably different results while satisfying one unchanged contract, and what identity must change when selecting between them?

## Reproduction and result

Reran the RT-11 synthetic C binding benchmark from `research/PROTOTYPES/DEPENDENCY-GRAPH-01` on CPython 3.12.14, Debian `cc (Debian 14.2.0-19) 14.2.0`, target `x86_64-linux-gnu`:

```sh
python3 -B -m src.binding_build_benchmark --cc cc
```

The fixture's initial contract permits base outputs 10 or 11. Its implementation changes from base 10 to base 11 without changing ABI or contract. The program validates complete execution tuples against that contract; clean-build oracles agreed with the incremental executions.

| Identity/binding question | Observed result |
|---|---|
| Does the declared contract change? | No; the same contract hash still allows both fixture outcomes. |
| Do implementation identity and execution result change? | Yes; the selected implementation changes from outputs `[10, 11, 10, 11]` to `[11, 12, 11, 12]`. |
| Can callers compile through a stable interface without seeing the changed body? | Yes in separate-link mode: 4 body-visible callers recompile, 12 prototype-only callers do not; all 12 affected executables relink and verification reruns. |
| Is caller compile identity sufficient to cache executable verification? | No. The caller compile-input digest is unchanged while executable observations change. Verification must bind the executable/result and contract (and the selected binding when policy requires it). |

Source SHA-256: `binding_build_benchmark.py` `8da49c2a49817ae429a4323b0aee02b8c866ea53cf796ab8c196cb191d745fe4`; `binding.py` `451fce52b0a01395339dab8f2d9c9901f155f1dac201a83efb588284e8187471`.

## Identity option comparison

- **O-A, contract-addressed OpHash:** consistent with this fixture. The OpHash can stay stable when the operation contract is unchanged; the new implementation receives a new `ImplHash`, and an explicit binding identifies which realization runs. A contract-level call may permit different outcomes by design.
- **O-B, body-sealed OpHash:** also coherent if the promise is that a call address names one body-level operation version. The OpHash changes on this implementation edit, even though the checked contract is unchanged. That trades transparent implementation substitution for a more exact call address.
- **O-C, contract OpHash plus BindingHash:** composes the two claims. Use OpHash for the abstract operation obligation and BindingHash for the exact implementation/target/evidence selection when reproducibility or deployment identity requires it.

The bounded observation supports keeping contract, implementation, binding and verification-action identities separate. It favors O-A plus explicit O-C binding at exact-execution boundaries over treating contract identity as a unique trace. It does **not** formally prove refinement, behavioral equivalence or substitutability for general LLMLang contracts: this fixture checks only four C input/output cases and one local ABI/compiler environment. State, effects, failures outside the declared inputs, target variation, contract completeness and trust in compatibility evidence remain unmodeled.

## Decision boundary and remaining dependencies

Before production substitution, LLMLang still needs formal pre/postcondition, invariant, effect, error and assumption semantics; a rule distinguishing equality, refinement and substitutability; complete binding/dependency identities; and evidence bound to exact operation, implementation, target, tool and assumptions. A permissive contract is meaningful only if consumers accept its allowed behavioral range. Adapter proof rules and human approval criteria remain open. No OpHash or BindingHash format is selected here.
