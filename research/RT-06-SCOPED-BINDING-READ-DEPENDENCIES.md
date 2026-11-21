# RT-06 — Negative dependencies in scoped binding resolution

**Date** · 2026-11-21  
**Baseline** · `b52ba2fb32e2c315997c74d8924c2c9aaeb177dc`  
**Status** · Bounded result for [Plan §3.1](../PLAN.md#31-semantic-dependency-model)

## Question

Can a resolver reuse the outcome of a scoped lookup when an unrelated row changes? A matching row can override an earlier provider. An invalid match or disallowed override can reject a lookup even when a valid, higher-priority provider is present. This matters for dependency recording and for cache reuse.

The experiment uses the existing scoped resolver, its exact contract and implementation checks, and project, tenant and request precedence. The observation is selected scope identity and implementation, or the exact rejection message. The resolution record's revision-bound root is outside this observation because it also commits to the consulted snapshots. [Scoped resolver](PROTOTYPES/DEPENDENCY-GRAPH-01/src/scoped_binding.py) · [Semantic dependency index](SEMANTIC-DEPENDENCY-INDEX.md)

| Key strategy | Consequence |
|---|---|
| All layer revisions and the policy | Retains full consultation context and invalidates when any consulted layer changes. Appropriate when that context is itself observable. |
| Highest-priority present row only | Reduces churn but loses lower candidates and negative lookup dependencies. It cannot account for all policy or contract rejection outcomes. |
| Exact per-key projection over all policy layers | Records absent layer, present layer with missing key, or exact matching contract and implementation. Includes scope identity, lookup key, required contract and policy. Can reuse the selected outcome while separately retaining evidence of the current consultation. |

## Results

The experiment exhausts six layer states across three scopes for two policies, yielding 432 views. Each state is absent, empty, unrelated, either of two exact providers, or a contract mismatch. The runner compares all 3,240 unordered transitions in which one scope changes.

| Key strategy | Outcome-preserving reuse in the measured transitions | False reuse |
|---|---:|---:|
| All layer revisions | 0 | 0 |
| Exact per-key projection | 216 | 0 |
| Highest-priority present row only | Not tallied | 516 |

With a valid request provider already selected, adding a lower project row with an incompatible contract preserves the highest-row key and changes the real outcome to rejection. With a project provider initially selected, inserting a tenant row can switch the result or reject it. The per-key projection changes in both cases.

The projection depends on valid complete input layers. A separate control adds a duplicate unrelated key. It leaves the per-key projection equal, but the resolver rejects the entire layer. A real cache must validate immutable layers before keyed reuse and must establish that its presence and absence answers describe the exact validated revision. Partial layers, unknown scope, or provenance-sensitive consumers require their own keys or a full revalidation. The model assumes trusted construction of scope policies and an immutable complete store. It provides no proof of completeness for dynamic or external resolution.

A per-key dependency is a candidate for reuse of selected outcomes under stated admission rules. The same projection cannot stand in for a new revision-bound consultation record or for general RT-20 completeness. [Semantic compilation cache](SEMANTIC-COMPILATION-CACHE.md) · [Dependency map](RESEARCH-DEPENDENCY-MAP.md)

## Reproduction

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`, run on CPython 3.12.14. The recorded run passed 13 tests. [Experiment](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_rt06_negative_binding_reads.py)

```sh
python -B -m unittest -v tests.test_rt06_negative_binding_reads tests.test_scoped_binding
```
