# Recursive and higher-order contract generator v1

Status: exploratory synthetic development profile; supports [#402](https://github.com/aivibeflow/LLMLang/issues/402), [#403](https://github.com/aivibeflow/LLMLang/issues/403), #394 and RT-33. Not normative LLMLang semantics or independent adjudication.

| Family | Distinguishing property | Scope |
|---|---|---|
| list_induction | Base and cons step; sum correctness | Lists length 0–5 over zero and nonzero parameter |
| tree_induction | Base and recursive node step | All binary shapes depth at most 3 |
| map_fusion | Higher-order composition vs reversed function order | All functions on a 3-element domain; empty, all singletons and one parameter-selected pair |
| function_extensionality | Equality of all function outputs | All pairs of functions on a 3-element domain |
| mutual_recursion | Both base/step obligations and parity | Integers 0 through a parameter-dependent bound 5–15 |
| least_fixed_point | Seed, closure, minimality and completeness | All subsets of six graph edges on 4 vertices; every root |
| greatest_fixed_point | Post-fixed relation, soundness and greatestness | All total successor maps and binary labelings on 3 vertices |
| stream_bisimulation | Equality of regular infinite streams | Every pair of pure periods length 1–4 over two labels |
| lasso_until | Strong vs weak until | All prefixes length 0–2 and periods length 1–2 over four p/q valuations |

The [profile](generative/recursive/profile.json) defines finite inputs and regular infinite models, not a general higher-order language or proof calculus. Candidate recursive functions, partition refinement, fixed-point iteration and cycle detection are checked against separately expressed oracles: mathematical sums, tree paths, finite relations, simple-path reachability, pair-product bounds and least-common-multiple stream scans. Strong until is decided exactly on each finite lasso representation; no general fairness or LTL model checker is claimed.

Every family has a reference, mutation and alternative; alternatives can be algorithmic rewrites. Base/step checks on bounded samples do not constitute induction proofs. The product-cycle argument for regular streams decides equivalence within the specified representation only; it cannot justify arbitrary coinductive definitions. A false observation retains an obligation-specific witness, replayed by the same checker; separately reasoned witnesses are in regression tests. Parameter records may share identical semantics (notably tree shapes); distinct record hashes do not imply distinct semantic instances.

## Reproduce

```sh
python research/PROOF-OBLIGATION-BENCHMARK/generative/recursive/test_recursive.py
python research/PROOF-OBLIGATION-BENCHMARK/generative/recursive/generate.py --count 90 --seed 42
```

Optional --output and --blind-output create new JSONL files; blind records omit variants and gold results but are not secret held-out data. CI stores code/profile hashes, corpus hash, counts and per-obligation failures. No verdict is promoted to proven.

## Formal backend targets

Lean: universal structural induction, mutual recursion termination, function extensionality and fixed-point theorems; explicit source/profile correspondence required. SMT: finite tables and bounded graph predicates where eligible. TLA+/TLC: finite transition/lasso properties with explicit temporal semantics and assumptions. These are proposed capability targets, not implemented adapters. General higher-order quantification, arbitrary coinduction, nonmonotone fixed points, unbounded recursion and richer temporal/fairness semantics remain open under #395 and #403. Independent review and private evaluation remain #404.
