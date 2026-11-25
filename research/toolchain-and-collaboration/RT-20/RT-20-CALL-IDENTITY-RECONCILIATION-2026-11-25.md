# RT-20 reconciliation of function versions and exact call references

RT-20 uses `hashId` as a workflow address for an exact immutable callable version in the supported prototype. Logical continuity, selected occurrence, public contract, concrete implementation, conformance class and proof receipt remain independently identified. A caller changes when an approved rewrite changes its exact selected references or other hash-relevant content.

## Identity crosswalk

| Study | Implication for the RT-20 call model |
| --- | --- |
| Study 05, stable identity and name-free core | A stable ID can track logical continuity across display renames and revisions. A call still needs its exact selected callable version. |
| Study 06, content-addressed immutable values | Rewriting a hash-relevant reference changes the caller version. Preserving an old exact target can retain its caller's address. |
| Study 07, content-only stress cases | Equal canonical values can share storage. Independently managed instances and lifecycles require explicit scope or lineage decisions. |
| Study 08, contextual occurrence addresses | A caller version can contain several distinct call sites and alternatives. An immutable occurrence address does not supply continuity across splits without selection or lineage. |
| RT-24 reconciliation | Keep semantic value, occurrence, selected snapshot, lineage and human-visible names distinct. The choice of canonical identity envelopes remains open. |

[Study 05](../../semantic-representation/RT-05/RESEARCH-SCENARIO-05-NAME-FREE-SEMANTIC-CORE.md) · [Study 06](../../semantic-representation/RT-05/RESEARCH-SCENARIO-06-CONTENT-ADDRESSED-ENTITY-IDENTITY.md) · [Study 07](../../semantic-representation/RT-05/RESEARCH-SCENARIO-07-CONTENT-ONLY-IDENTITY-STRESS-TESTS.md) · [Study 08](../../semantic-representation/RT-05/RESEARCH-SCENARIO-08-OCCURRENCE-ADDRESSING.md) · [RT-24 identity and SPG report](../RT-24/RT-24-IDENTITY-AND-SPG-RECONCILIATION.md)

In declaration schema v2, each call alternative binds an exact callee and the required Contract hash. The selected callee declaration owns the provided-Contract reference. A rebind decision preserves the caller requirement, exact old and new selection, path and applicable evidence. A changed Contract is a distinct compatibility question even when a declaration's reference can be rehashed. The current workflow uses `hashId` without assigning it the normative meaning of `OpHash`, `ImplHash` or `CCHash`. [RT-20 contract identity](RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md) · [Workflow assumptions](RT-20-LLM-PATCH-PLANNING-AND-HASH-PROPAGATION.md)

## Reconciled evidence

The checker validates three ledgers. Across 2,376 native invocations, the propagation fixture preserves five baseline hashes and rebinds five dependent roles. Three consumer forks yield six exact path-bound decisions where the original key distinguishes two. An omitted decision remains undetected by the supplied-row materializer unless the caller inventory is checked independently. Across 704 RT-24 lineage profiles, equal content under a distinct stable identity cannot substitute an authorized occurrence, and a receipt for one split caller cannot support the other.

These results support distinct workflow identities and exact call references in the tested profiles. General dynamic closure, authoritative call extraction, recursive group identity, and normative terminology remain separate research and decision gates. [Native caller propagation](RT-20-NATIVE-CALLER-PROPAGATION-2026-11-25.md) · [Consumer fork identity](RT-20-CONSUMER-FORK-IDENTITY-2026-11-25.md) · [Lineage and rebinds](../RT-24/RT-24-IDENTITY-LINEAGE-AND-REBIND-2026-11-25.md)

## Reproduce

CPython 3.12.14 with Python hash seeds 37 and 71 yields evidence SHA-256 `f8526a836fd80b034e72eacde387b80c760c6fa8277f06ef246581347ea1f012`. [Reconciliation ledger](CALL-IDENTITY-RECONCILIATION-01/evidence.json)

```sh
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python research/toolchain-and-collaboration/RT-20/CALL-IDENTITY-RECONCILIATION-01/check.py > /tmp/rt20-call-identity.json
```
