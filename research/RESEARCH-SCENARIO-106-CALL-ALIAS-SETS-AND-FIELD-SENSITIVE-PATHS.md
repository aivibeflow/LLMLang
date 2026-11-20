# Research Scenario 106 — Call-Site Alias Sets and Field-Sensitive Paths

**Status:** exhaustive finite alias-target comparison; no alias or effect system selected
**Research areas:** RT-03 mutable state; RT-04 effects and aliasing; RT-06 path/dependency completeness
**Updated:** 2026-11-19

## 1. Question

When a callee writes through a reference, how much state must the caller's path analyzer invalidate? Does field-sensitive mutation information help, and what happens when the call-site alias set is incomplete?

## 2. Fixture

The caller has two mutable Boolean fields, `flag` and `other`, branches on `flag`, calls `toggle(&arg)`, and branches on `flag` again. `toggle` changes the Boolean field designated by its reference argument. The pre/post route set is exhaustively computed across both initial field values and possible alias targets. The executable model is [`rt03_alias_sensitive_call_paths.py`](PROTOTYPES/RT-04-01/rt03_alias_sensitive_call_paths.py); tests are in [`test_rt03_alias_sensitive_call_paths.py`](PROTOTYPES/RT-04-01/test_rt03_alias_sensitive_call_paths.py).

| Call-site alias evidence | Possible target(s) | Post-call routes for `flag` | Precision/soundness |
|---|---|---|---|
| Exact points-to | `{flag}` | `FT`, `TF` | Exact for the toggle summary |
| Exact disjoint field | `{other}` | `FF`, `TT` | `flag` remains stable because the target is proven disjoint in this fixture |
| May-alias set | `{flag, other}` | All four | Sound union of the transition relations; two routes are spurious for any one concrete target |
| Unknown/incomplete alias set | Any modeled reachable field | All four | Conservative havoc; does not assume that `flag` is unchanged |
| Incorrect no-alias assumption | Treat as `{other}` despite real `{flag}` possibility | Only `FF`, `TT` | Unsound; drops the concrete `FT`/`TF` routes for the `flag` target |

The test domain exhausts two initial bits and the two candidate reference targets. Five focused tests pass. The states and call summary are hand-authored; this does not implement points-to analysis.

## 3. Findings

1. The effect summary (`writes through this reference`) and the call-site points-to set answer different questions. Path transfer must compose them: possible concrete targets are the intersection of the callee's write footprint with call-site reachable locations.
2. Field-sensitive evidence can preserve unrelated fields and avoid unnecessary path broadening when disjointness is proven.
3. A may-alias set must union the possible state transitions. An incomplete alias set cannot be treated as complete merely because the callee's declared write set is narrow.
4. Unknown aliasing conservatively broadens path and dependency results. This is the same soundness boundary established for unknown call effects in Scenario 105, now applied to concrete call-site locations.

No language-level reference, ownership, alias, or effect policy is selected. A candidate analyzer needs explicit provenance/completeness for both the callee effect summary and call-site alias set before it may prune a caller path.

## 4. Limits and next discriminators

The model has two Boolean fields, one synchronous call, a known toggle body, and a direct reference argument. It excludes nested objects, arrays, pointer arithmetic, escape, re-entrance, dynamic dispatch, call failures, concurrency, and source-level points-to extraction. The "unknown" set is bounded to the modeled region; a real analyzer must account for all reachable memory it cannot prove disjoint.

Next compare field-sensitive versus object-wide invalidation on larger object graphs, strong versus weak updates under may-alias, escaping references, transitive/dynamic call targets, and calls that mutate before returning an error or cancellation. Bind the alias set and effect summary to the same immutable source/IR revision and preserve UNKNOWN if either input is stale or incomplete.

## 5. Reproduction

From `research/PROTOTYPES/RT-04-01`:

```sh
python -m unittest -v test_rt03_alias_sensitive_call_paths.py
python rt03_alias_sensitive_call_paths.py
```
