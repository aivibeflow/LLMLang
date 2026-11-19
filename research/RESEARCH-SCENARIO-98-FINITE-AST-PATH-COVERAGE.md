# Research Scenario 98 — Finite AST-to-Path Coverage

**Status:** bounded path-witness experiment; no source parser or path-extraction policy selected  
**Research areas:** RT-03 control-flow observation, RT-04 resource obligations  
**Updated:** 2026-11-19

## 1. Question

For a declared finite expression-tree grammar, does the independent structural path model enumerate every feasible branch/resource observation, and does every predicted path have a concrete input witness executed by both RT-03 evaluators?

This narrows COR-06's open gap. The experiment addresses abstract Boolean branch markers in the supplied AST fixture. It does not claim that a future source parser, AST builder, or CFG extractor would preserve every LLMLang source branch.

## 2. Method

The generated tree is a full binary decision tree of depth three, wrapped in an outer resource scope. Each of its seven `unknown_bool` conditions has a unique marker. Its eight leaves carry unique resource IDs and vary among ordinary return, explicit `Result` error, and cancellation; selected leaf and outer cleanup actions fail. The unique resource trace acts as a path witness.

The experiment then:

1. Enumerates paths with `rt03_path_model.enumerate_paths`.
2. Enumerates all `2^7 = 128` assignments of concrete Boolean inputs and substitutes literals for the abstract markers.
3. Executes each concrete tree in both the recursive and small-step evaluators.
4. Compares complete effect event sequences and final resource maps between evaluators, then compares resource-event sequence, active resources, terminal kind, Result tag, and cleanup-error order against the path model.
5. Verifies every syntactic condition is represented among the predicted branch choices and each predicted path has a concrete witness.

The focused regression lives in [`test_rt03_path_model.py`](PROTOTYPES/RT-04-01/test_rt03_path_model.py), named `test_exhaustive_ast_condition_valuations_cover_every_structural_path`.

## 3. Result

All 128 concrete assignments produced observations in the set of eight predicted structural paths. The eight path observations had unique resource-trace witnesses, all seven condition nodes appeared in the path model's branch-choice set, and each path had a concrete assignment witness. For every assignment, recursive and small-step evaluators produced identical complete event sequences and final resource maps; their projected observations matched the path model's terminal, Result, cleanup, and active-resource fields.

This provides finite corroboration that the path model covers this generated AST grammar and fixture protocol. The same code does not establish that the grammar is a complete source language or that an extractor maps source programs to these trees without omissions.

## 4. Limits and next evidence

- Conditions are independent Boolean inputs; symbolic predicates, repeated correlated conditions, and infeasible paths are not modeled.
- The experiment uses hand-generated ASTs, not parsed LLMLang source or an independently implemented parser.
- Unique fixture resource IDs expose branch witnesses; general programs may have observationally equivalent paths.
- Calls, mutable locals, effects beyond resource operations, divergence, async cleanup, and dynamic resource aliases are outside the tree.
- The two evaluators share the same exploratory semantic contract. Agreement is implementation cross-checking, not independent specification review or proof.

Next evidence should bind a real parser/IR extractor to a frozen grammar revision, add repeated conditions with satisfiable/unsatisfiable predicates, and audit source-node-to-IR-node coverage before generalizing path completeness.

## 5. Reproduction

From `research/PROTOTYPES/RT-04-01/`:

```sh
python -m unittest -v test_rt03_path_model.RT03IndependentPathModelTests.test_exhaustive_ast_condition_valuations_cover_every_structural_path
```

