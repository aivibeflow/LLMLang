# RT-00 — Orthogonal falsification of three bounded Stage 0.2 claim families

**Date:** 2026-11-23  
**Status:** New orthogonal Python oracle and Git negative-control checks proposed, pending GitHub Actions result  
**Research item:** [issue #285](https://github.com/aivibeflow/LLMLang/issues/285), [PLAN §0.2](../PLAN.md#02-establish-research-quality-and-decision-rules)  
**Prior claim cohort:** [12 reports and 24 claims](RT-00-QUALITY-RULES-CLAIM-COHORT2-2026-11-23.md); [three existing-source reruns](RT-00-QUALITY-RULES-CLAIM-COHORT2-RERUN-2026-11-23.md)  
**Audited model source revision:** `ff1295c1769bfe8546c4b63590c9f607349215ee`  
**Evidence type:** New independent-*implementation* reference decision tables and negative fixture, *not* independently peer-reviewed science  
**Draft impact:** **None.** No LLMLang language, wire, fairness or merge requirement is accepted.

## 1. Question, hypotheses, prior art

The three original test suites in [PR #381](https://github.com/aivibeflow/LLMLang/pull/381) passed on archived source. Re-running the same test code can reproduce its observations without providing evidence that the test's expected values were correctly derived. This study introduces separate code/decision tables, including inputs not covered by the original finite fixtures.

- **H1 (testable):** Scenario 110's parser/policy adapter agrees with a separately written declarative reference decision table for 1,728 combinations of count, enabled, unknown field, version, defaults and null policy, including invalid inputs. All inputs use the tested model's *JSON object* domain.
- **H2 (testable):** Scenario 112's finite cycle helper agrees with a separately written enabledness transition table and weak/strong fairness interpretation on 21,840 short action words, including illegal/non-cyclic candidates.
- **H3 (negative control):** A real Git merge can exit successfully while the merged tree lacks an explicitly declared source file. Restoring the declared file repairs the closed inventory without selecting a general semantic-merge policy.

**Alternatives:** Re-run original tests only (no distinct oracle); compare source text for equality (does not establish semantics); or implement separate model-level oracles plus falsifying negative controls. We use the last, without claiming that matching two implementations proves all production semantics.

**Prior-art inputs:** [Scenario 110](RESEARCH-SCENARIO-110-WIRE-SCHEMA-EVOLUTION-AND-DEFAULTS.md), [Scenario 112](RESEARCH-SCENARIO-112-WEAK-STRONG-AND-BOUNDED-FAIRNESS.md), [RT-24 merged-tree gate](RT-24-MERGED-TREE-SOURCE-COMPLETENESS.md), [first evidence-shape and decision rules](QUALITY-REVIEW-PROTOCOL.md).

## 2. Fixed model and executable methods

The [orthogonal test source](../.github/scripts/test_research_orthogonal_oracles.py) is intentionally distinct from the original author test classes. In a new CI checkout it imports the two *original model implementations* from a pinned archival Git commit while deriving all expected outcomes in separately authored functions.

| Vector | Independent method | Expected observation | What is shared or unproved |
| --- | --- | --- | --- |
| JSON schema/defaults | Declarative field-presence/type/unknown-policy decision table, over 8 `count` values × 9 `enabled` values × 3 extra-field states × 2 wire readers × 2 unknown policies × 2 defaults × 2 null policies = **1,728** cases | Agreement for success/reject and exact accepted `(count, enabled)` values | Both sides trust Python's JSON parsing; duplicate JSON member canonicality is *out of scope* |
| Finite fairness | Separate enabledness transition table, enumerating **21,840** action words of lengths 1–6 for two enabledness starts and intermittent/continuous modes; independent cyclic validity and periodic weak/strong fairness classifications | Legal cycles and rejection status agree; strong fairness for starvation implies weak fairness; intermittent weak-but-not-strong witness exists | Both sides use the same abstract enabledness assumptions; no real runtime fairness |
| Git closure control | Create disposable real Git repository, delete a declared semantic source in one branch, edit unrelated file in other branch, merge cleanly, compare `ls-tree` file inventory to manifest; then restore source | Git clean merge is **not sufficient** for declared inventory closure; explicit retained source restores closure | Does not test LLMLang's SPG importer, source parser, hash model, or production semantic merge |

The JSON test additionally rejects malformed and non-object payloads and records a **non-claim**: Python's JSON decoder accepts duplicate `count` members with last-member-wins behavior. This is a known domain/canonicality limitation, **not** an incorrectly asserted defect in Scenario 110. It must never be transformed into a general serializer assurance.

**Fixed test/model blobs at the archival commit:**
- `schema_evolution_model.py`: `59a3a8b2fdd3bd2b2d6167a7f5cedb02551e512e`.
- `scheduler_fairness_model.py`: `1309f21c4ce49f8584f03782e742549fc7d817d9`.
- RT-24 negative fixture uses **independent Git CLI setup**, not shared original test code. Its scope is therefore the simple closure counterexample, not RT-24's full graph audit.

## 3. Reproduce and expected outputs

[GitHub Actions workflow](../.github/workflows/research-quality-orthogonal-oracles.yml) checks out both the PR's new oracle and the exact archival model commit. Before running it verifies model Git blobs; then it runs seven Python standard-library tests in CPython **3.12.14** on Ubuntu 24.04 and archives the environment and log:

```sh
LLMLANG_ORACLE_MODEL_DIR=archival/research/PROTOTYPES/RT-04-01 \
  python3 -B -m unittest discover \
  -s .github/scripts -p 'test_research_orthogonal_oracles.py' -v
```

**Expected before independent execution:** seven tests pass and markers `INDEPENDENT_SCHEMA_CASES=1728`, `INDEPENDENT_FAIRNESS_WORDS=21840`, `INDEPENDENT_GIT_WITNESS=clean-merge-with-missing-declared-source` appear. An unexpected mismatch or missing Git object is a **failure to investigate**, not evidence for accepting a design choice.

**Observed results:** *pending GitHub Actions*. A passing original author's test suite is prior evidence and not a substitute for the new oracle's independent execution.

## 4. Negative results, trust boundaries and decision safety

Even if all checks pass:

- **The reference oracle is independently implemented, not independently reviewed by another human.** It may share the same mistaken specification assumption with the original model; the CI runner only supplies a fresh execution environment.
- **Finite JSON decoding does not prove canonicality, trust policy, language wire compatibility, parser ambiguity resistance, binary formats, unknown-enum preservation or schema migrations.** The duplicate-member fixture demonstrates a concrete unhandled policy dimension outside the selected model.
- **Finite periodic fairness is not real scheduler liveness, progress under external blocking, thread safety, or quantitative response bound.**
- **Git can merge text cleanly while semantic source is missing;** the independent negative witness supports the necessity of source-inventory checks. It does not demonstrate that every LLMLang source->SPG mapping is complete or that a production merge protocol is correct.
- The original eight historical-run provenance gaps remain open. Replaying archival code under new CPython/Git does not attest the initial experimenter's state.
- An independent reviewer still must inspect claims, adversarial test adequacy, missing unknown cases, falsifiers, and the proposed Q1–Q5 policy before any process adoption.

**Recommendation:** keep warning-first research documentation and source-bound evidence classes. For a research-methods decision, a maintainer should independently inspect the falsifier coverage and the eight outstanding historical provenance issues. For a semantic design decision, require separate owning RT/ADR evidence and an explicit `draft/` change proposal.

**No status promotion:** issue #285 remains **Open / research in progress**; this experiment does not close global acceptance criteria or adopt quality rules.
