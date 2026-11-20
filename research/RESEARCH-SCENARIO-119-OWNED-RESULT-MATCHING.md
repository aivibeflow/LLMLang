# Research Scenario 119 — Ownership in Matched Call Results

**Status:** executable comparison of transfer timing and result types in a bounded call fragment

**Research areas:** RT-03 execution · RT-04 types and ownership · RT-05 interface identity

**Updated:** 2026-11-20

## Question

Can the checker derive what a caller must forward when either a function body or its cleanup fails? COR-13 already records the resource transitions and checks hand-written caller branches. This experiment derives the branches from the callee's body and cleanup contracts, then tests the caller's match against them. [COR-13](RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md)

## Fragment and alternatives

The callee is a named function with two nested owned scopes. Its body selects a domain error or an explicit move of the outer handle. The inner scope owns a temporary. Each scope declares the set of outcomes its close operation can report: success, error after consumption, error with retention, or unknown resource state. In the staged policy, the move commits after the temporary closes successfully. If the temporary close fails, the callee attempts to close the pending handle. In the earlier transfer policy, the successful body moves the handle before the temporary closes. The domain error case precedes transfer in both policies.

The checker computes a set of result shapes from that body and the possible close outcomes. A shape records the result tag and the obligations that can accompany it. A returned handle carries `owned`. A failed close with known retention carries `retained`. An indeterminate close carries an abstract `reconcile` obligation whose recipient must resolve the state before acting on the resource. Consumption with error contributes a diagnostic. The obligation slots refer to the two roles in the contract, so renaming a private callee binding leaves the shape unchanged.

The caller matches each reachable shape and forwards every obligation exactly once. The experiment compares two output types:

| Output type | What an error can forward | Match requirement |
|---|---|---|
| `Result<Owned<Handle>, Diagnostic>` | Body error and ordered cleanup diagnostics | The error arm must have discharged any resource obligations. This fragment only forwards, so the checker accepts it when those arms carry no obligations. |
| Result with tagged obligations | Body and cleanup diagnostics plus the returned value, retained obligations, or reconciliation obligations specified by each case | One arm per reachable shape. Each arm forwards every obligation with its inferred kind. |

The second design can use a tagged `E` inside `Result<T, E>`. Rust's `Result` is generic over `E` and its match patterns can move values out of a variant. The experiment compares the expressiveness of the payload and the work required in the caller. [Rust `Result`](https://doc.rust-lang.org/std/result/enum.Result.html) · [Rust match expressions](https://doc.rust-lang.org/reference/expressions/match-expr.html)

## Evidence

For each resource, the experiment checks all 15 nonempty subsets of the four declared close outcomes. The two transfer policies give 450 combinations of callee contracts. Enumerating both branches and every permitted pair of close results gives 4,096 concrete fixture inputs, including inputs whose handle close is unneeded on the selected branch. For every contract, the sets of result tags and obligation kinds inferred from the AST matched the sets observed when running the separate COR-13 disposition model. [Checker and execution adapter](PROTOTYPES/RT-04-01/rt04_owned_call_match.py) · [Disposition model](PROTOTYPES/RT-04-01/rt04_return_disposition.py) · [Fixtures](PROTOTYPES/RT-04-01/test_rt04_owned_call_match.py)

| Transfer policy | Diagnostic-only `Err` accepted | Tagged forwarding accepted | Exact arms when both close contracts allow all four results |
|---|---:|---:|---:|
| Transfer before cleanup | 3 of 225 | 225 of 225 | 14 |
| Commit after cleanup | 9 of 225 | 225 of 225 | 20 |

These counts describe forwarding under the fixture contracts. Early transfer puts the returned handle in an error arm whenever the temporary's close fails, even if that close consumes the temporary. A staged return can forward a diagnostic alone when the failed cleanups leave neither a retained capability nor an unknown state. Staged failure can also require cleaning the pending handle, leading to more combinations of obligations. This increases the number of exact arms under the widest contract. When both closes report consumption with error, the plain error still preserves both cleanup diagnostics in order along with the original domain error.

Changing the temporary's contract from consumed-on-error to consumed-or-retained leaves the set of result tags unchanged in the staged failure example. It introduces new payload shapes. The previous exhaustive caller is rejected with missing arms. Accordingly, compatibility checks for this kind of API need to inspect the obligations behind the tags.

Ten focused tests passed on Python 3.12.14 at base `9e6c294` with the Scenario 119 changes.

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_owned_call_match.py' -v
```

## Limits and next discriminator

The experiment uses a hand-built AST with one named direct call and two scopes. Caller arms forward their inputs. Local recovery, resource aliasing, cancellation, recursion, a parser, and a real OS adapter remain open. The execution comparison reuses the COR-13 model under the same disposition assumptions. A `reconcile` obligation stands for an API-specific recovery mechanism the candidate would need to provide. It grants no permission to close or reuse the original resource. The next comparison should give the caller an explicit recovery branch and compare discharging obligations locally with forwarding them upstream.
