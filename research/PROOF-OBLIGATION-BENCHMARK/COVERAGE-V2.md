# Extended coverage inventory and generative benchmark v1

Status: exploratory, non-normative, public development material. Supports #394, [#402](https://github.com/aivibeflow/LLMLang/issues/402), [#403](https://github.com/aivibeflow/LLMLang/issues/403), [#404](https://github.com/aivibeflow/LLMLang/issues/404). Preserves the existing 80-cell finite matrix; does not redefine its meaning.

## Multi-axis coverage

The [registry](coverage-v2.json) separates semantic features, logical structure, program levels and interactions. Existing POB case references are candidate links, not claims of adequate coverage. Generated family links likewise indicate relevant syntax, not full domain semantics. The 300-cell original form × domain × scenario inventory is emitted with candidate IDs, case-level probe IDs, and explicit unadjudicated applicability. A missing co-occurrence is not automatically an applicable gap; an existing co-occurrence is not a verified witness. No cell is declared independently adjudicated.

| Axis | Entries |
|---|---:|
| features | 27 |
| logic | 13 |
| levels | 9 |
| interactions | 8 |

Next: adjudicate applicability per cell (required or not applicable with semantic rationale), attach an exact obligation and isolated executable witness for each required cell, and preserve reviews and revisions. Extend to pairwise interactions and selected higher-order combinations. Candidate RT-03 profiles remain distinct: pure, imperative/linear, actor/concurrent and effectful functional. See [RT-03](../RT-03/CORE-LANGUAGE-SEMANTICS.md). Do not invent normative semantics for unresolved profiles.

## Executable generator

The [grammar](generative/grammar.json) admits typed closed finite integer/Boolean formulas, arithmetic, equality/order, connectives and bounded quantifiers with explicit scope/limits. Unsupported constructs are rejected. Six parameterized families cover intervals, arithmetic equality, universal-existential, existential-universal, unique existence and guarded caller/callee composition. Each has a reference, mutation and equivalent alternative. A separate direct relation implementation (not AST evaluation) checks the template outcome; the interpreter checks the AST and emits counterexample or exhaustive failed existential scan. Neither implementation is independently adjudicated. The shrinker preserves the family and mutation failure, not a proof of minimal syntax. Shift invariance is a metamorphic control.

```sh
python research/PROOF-OBLIGATION-BENCHMARK/coverage_v2.py > coverage-v2-report.json
python research/PROOF-OBLIGATION-BENCHMARK/generative/test_generator.py
python research/PROOF-OBLIGATION-BENCHMARK/generative/generate.py --count 10000 --seed 42
```

Use optional `--output corpus.jsonl` to create a new file containing complete formulas and gold outcomes. Do not feed that file to evaluated models. The summary records exact corpus digest, code digests, seed, distinct formula triples, family distribution and mutation count. Re-run with identical code and seed to reproduce. A different seed may overlap the public family space; never call it independent held-out data. Ten thousand syntactically distinct parameterizations of six families are not ten thousand distinct semantic classes. All runs are bounded finite checks, not proofs.

## Recursive and regular-infinite profile

See [recursive and higher-order contract generator](RECURSIVE-GENERATOR.md) for nine new candidate families under recursive/. These do not establish universal induction or arbitrary coinductive correctness.

## Remaining work

- #402: real strings/Unicode, geometric predicates, external APIs, clocks, inductive and coinductive properties, higher-order and effectful contracts, whole-system workloads, reviewed applicability and interaction witnesses.
- #403: typed state/trace/effect/heap grammars, richer mutation operators, general semantic shrinking, blind stage exports and generator-independent formal oracles.
- #404: independent reviewers and private family-disjoint frozen evaluation sets.
- #395/#397: real proof backends, unsupported/unknown/error and evidence composition/invalidation.
- #396: actual LLM experiments with reviewed cases and reproducible scoring.

No absolute contract completeness claim follows from this inventory or generated sample.

## Transition profile update

See [finite transition contract generator](TRANSITION-GENERATOR.md) for nine additional parameterized families, typed state/action grammar, trace oracle, per-obligation witnesses and blind export. Registry links use the transition/ prefix and remain unreviewed candidates.

## Structural and system profile update

See [structural and system contract generator](SYSTEM-GENERATOR.md) for seven additional families, reachable-state exploration, replayable obligation witnesses and candidate registry links under system/. These links do not imply independent adjudication or full separation logic/consensus semantics.
