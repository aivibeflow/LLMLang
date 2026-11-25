# RT-02 — Resolve clarification conflicts only within their authorized scope

## Question and method

When a later clarification covers a narrower group of cases than an existing requirement, can it replace the earlier source without silently losing the rule elsewhere? The [typed provenance study](RT-02-CLAUSE-PROVENANCE-AUTHORITY-2026-11-25.md) binds exact source excerpts and an explicit replacement for one clause field. This study extends the fixture to overlapping scopes and an independent failure obligation. It uses the baseline `0ef40055665a73b82c6ac30c2ea88f71b8947331` on `research/all`.

The declared domain has retail and wholesale orders, each with successful or failed reservation. Successful orders need a grounded deadline and failed orders need a grounded automatic-confirmation prohibition. The synthetic sources propose a five-second deadline for all successes, a seven-second deadline for retail successes, and a prohibition for all failures. The fixture treats selected attestations as source interpretations and checks their exact identities and stipulated authority. It compares implicit resolution by narrowness with an explicit authority-bound override.

```mermaid
flowchart LR
  S["Exact source attestations"] --> V["Verify revisions, authority and override target"]
  V --> P["Partition the declared scope into obligation cells"]
  P --> A["Select applicable current support per cell"]
  A --> G["Record grounded value, conflict or uncovered cell"]
  G --> R["Bind only grounded cells to typed clause support"]
```

A replacement must name an exact earlier attestation for the same claim field and apply within its scope. It suppresses that attestation only in the cells where the replacement applies. Coverage is evaluated per field and cell. An uncovered cell remains open, including when adjacent cells are grounded. The existing provenance study provides the subsequent exact links to the formal and reconstructed clauses.

## Results

| Control | Observed disposition |
|---|---|
| Five-second default and separate failure prohibition | All four cells are grounded. |
| Narrower seven-second statement without an explicit override | Retail success has two conflicting values. Wholesale success retains five seconds and the failure cells retain the prohibition. |
| Seven-second statement with an exact authorized override | Retail success uses seven seconds. Wholesale success keeps the earlier five-second value. Both failure cells keep the prohibition. |
| Retail deadline with no wholesale source | The wholesale-success cell is uncovered. The retail and two failure cells retain their support. |
| Broader override, missing exact target, stale source, unauthorized source or unsupported scope | The purported support is insufficient. The fixture keeps the package unknown and records the specific defect. |

All nine controls matched their declared outcomes. An implicit preference for the latest or most specific source would hide the unresolved conflict in the first narrow-rule case. A global replacement would remove evidence for the wholesale rule in the valid local case. LLMLang can represent both facts by recording exact affected scope and retaining the prior attestation outside the override. [Selected source IDs, cells and defect codes](SCOPED-PROVENANCE-01/evidence.json)

This study specifies traceability and override rules for a closed, finite scope representation. It leaves general discovery of source completeness, equivalence or overlap of arbitrary predicates, external stakeholder authentication, and validation of the source interpretation itself open. The evidence is a candidate model and does not establish a production conflict-resolution policy. [RT-02 tracking](https://github.com/aivibeflow/LLMLang/issues/287)

## Reproduction

Use CPython 3.12.14. The [runner](SCOPED-PROVENANCE-01/run.py) records the exact source strings, attestations and source hashes. All dispositions and the named defect distinctions are asserted. Hash seeds 1 and 2 produced identical output. The diagram was checked as Mermaid source.

```bash
fixture=research/language-design/RT-02/SCOPED-PROVENANCE-01
LC_ALL=C PYTHONHASHSEED=1 python3 -B "$fixture/run.py" > /tmp/llmlang-rt02-scoped-provenance.json
cmp "$fixture/evidence.json" /tmp/llmlang-rt02-scoped-provenance.json
```
