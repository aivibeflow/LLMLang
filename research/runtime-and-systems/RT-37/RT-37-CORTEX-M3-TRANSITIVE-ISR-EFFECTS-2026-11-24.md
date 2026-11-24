# Transitive interrupt effect admission from Cortex-M3 binaries

- **Date:** 2026-11-24
- **Research:** RT-37 EMB-05/06, RT-04 and DEP-246
- **Baseline:** `492e48fc4031f5cda9f2d607b39fb59f767ee23e`
- **Evidence:** Seven exact linked Thumb artifacts and three effect-admission inputs to the same RT-04 checker

An interrupt's direct effect set can be empty while a reachable helper blocks or reserves memory. The linked-call approach admits two control-flow shapes for acknowledging SysTick, rejects three artifacts with known forbidden effects, and returns `UNKNOWN` for an unresolved target and a stale primitive contract. Local effects and an unchanged supplied graph admit all seven.

## From vector to effect bound

The replay reads vector slot 15 from each ELF and verifies the exact Thumb symbol selected by the vector. The admitted decoder follows direct `bl` call targets and `b` branches to other function entries. It uses the exact function extents from the symbol table. `blx` through a register leaves target coverage open. Control, memory or fall-through behavior outside the profile likewise leaves coverage open. The checker reads `wfi` as a possible blocking operation. A separately reviewed leaf provision identifies the single-bit `ICSR` acknowledgement and the bump-reservation helper by their exact linked body hashes. The probe uses encoded immediate addresses so those bytes cover the addressed locations.

The [RT-04 checker](../../PROTOTYPES/RT-04-01/README.md#transitive-effect-bounds) computes the transitive effect union and checks the root against the singleton bound `mmio.systick.acknowledge`. Matching leaf effects supply premises for the experiment. Every reachable function must have closed target and effect coverage before the bound can pass. A known forbidden effect is a definite rejection even when another edge remains unresolved.

| Linked control | Root-only | Reused supplied graph | Exact linked-graph judgment |
| --- | --- | --- | --- |
| Direct helper reaches `ICSR` acknowledgement | Accepted | Accepted | Accepted |
| Tail-branch adapter reaches `ICSR` acknowledgement | Accepted | Accepted | Accepted |
| Two calls reach `wfi` | Accepted | Accepted | Rejected, `irq.block` |
| Two calls reach bump reservation | Accepted | Accepted | Rejected, `allocation.bump` |
| Indirect call target unresolved | Accepted | Accepted | `UNKNOWN` |
| Reachable `wfi` and unresolved indirect call | Accepted | Accepted | Rejected, with unresolved coverage retained |
| Acknowledgement body changed from clear-pending to set-pending | Accepted | Accepted | `UNKNOWN`, primitive evidence revision mismatch |

All seven images contain the blocking and allocation helpers. The accepted cases depend on reachability from the vector, so whole-image presence alone would reject both. The final control keeps a leaf symbol and call edges stable while changing an instruction. The old leaf receipt cannot authorize the changed behavior.

## Reproduce and scope

Use LLVM/LLD 19.1.7 and Python 3.12.14. The [ledger](cortex-m3-isr-effects/results.json) records every exact ELF hash, vector, leaf hash, edge, effect and unresolved reason. Two independently linked replays reproduced it byte for byte. The 52 existing focused RT-04 checker tests also passed.

```sh
fixture=research/runtime-and-systems/RT-37/cortex-m3-isr-effects
output=$(mktemp)
python3 -B "$fixture/run.py" --output "$output"
cmp "$fixture/results.json" "$output"
```

This is a binary admission experiment for a small linked Thumb instruction profile. It relies on trusted primitive effect facts and the ordinary call/return discipline of the fixture. The negative images serve as static inputs. Indirect target completeness, full LLMLang source-to-binary correspondence, allocator progress, capability issuance and hardware timing remain separate obligations.
