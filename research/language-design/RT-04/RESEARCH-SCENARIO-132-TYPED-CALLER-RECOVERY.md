# Research Scenario 132 — Typed Recovery in the Caller

**Status:** bounded source match and differential execution on the COR-13 workload

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

When can the caller recover from an owned-result error before attempting an aliased foreign operation? Scenario 131 forwards the original obligations and checks the next proposal. This scenario compares forwarding with an explicit release on an error arm that carries a usable handle. [Shared owned-result workload](RESEARCH-SCENARIO-131-SHARED-OWNED-RESULT-WORKLOAD.md)

## Source and authority

Both source fixtures add a result match before the second proposal. The checker derives four groups from the callee's result shapes. A successful result carries the original value. An error can carry a usable handle, a reconciliation obligation for the handle, or no handle obligation. Local cleanup obligations remain distinct from the handle's authority. [Source and type checks](../../PROTOTYPES/RT-04-01/rt04_shared_owned_handlers.py)

```python
match outcome:
    case "success":
        preserve()
    case "error_with_handle":
        release_first()
    case "error_reconcile":
        preserve()
    case "error_without_handle":
        preserve()
```

The forwarding fixture uses `preserve` in all arms. The recovery fixture calls `release_first` only where the declared contract guarantees a usable handle with release authority. Missing and duplicate branches fail the exhaustiveness check. A release in an arm with an unresolved or absent handle fails the authority check. [Focused tests](../../PROTOTYPES/RT-04-01/test_rt04_shared_owned_handlers.py)

On a caller release, `ok` and a consuming error remove the earlier roles. A retaining error or an indeterminate outcome keeps the possible role footprint and forwards the corresponding obligation. The caller preserves any separate scratch obligation and adds its cleanup diagnostic in order. It checks the aliased proposal against the roles after the selected arm. [Prior disposition evidence](../../compiler-and-translation/RT-13/RESEARCH-SCENARIO-128-FOREIGN-RESERVATION-OUTCOMES.md)

## Results

Each of the 5,184 inputs from Scenario 131 is paired with four possible outcomes of caller release. This gives 20,736 inputs per fixture, including paths where the caller performs no release. The independent test oracle starts from the direct transition evaluator and recomputes caller effects and compatibility. The fixtures and oracle agree on the chosen branch, effects, diagnostics, forwarded obligations, reservations, and admission. [Oracle and generated inputs](../../PROTOTYPES/RT-04-01/test_rt04_shared_owned_handlers.py)

| Callee transfer order | Proposals started with forwarding | Proposals started with recovery | Caller releases | Caller releases on already admissible proposals | Additional starts after a consuming error |
|---|---:|---:|---:|---:|---:|
| Before cleanup | 1,728 | 2,688 | 3,456 | 384 | 480 |
| After cleanup | 2,448 | 2,868 | 1,512 | 168 | 210 |

Recovery admits 1,380 additional proposals. Exactly 690 are enabled by a consuming error. It also performs 552 releases on inputs where the proposed roles were already compatible. Releases append a diagnostic in 3,726 inputs. Admission alone therefore measures only one part of the difference. The policy changes observable effects and which obligations the caller forwards.

For `a → b` followed by `c → b`, an error carrying the first handle gives the caller authority to attempt release. A consuming error allows the second start and leaves any scratch obligation visible. An uncertain disposition keeps the first role pair unavailable to a conflicting proposal. The fixture carries the original callee outcome and the obligations after the caller action as separate observations.

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_shared_owned_*.py' -v
```

The runs used Python 3.12.14. The grammar covers the fixed callee and one unguarded result match. The release outcome is a fixture input, and admitted proposals start in the model. General source patterns, conditional recovery inside arms, runtime FFI authority, and correspondence across complete language profiles remain open.
