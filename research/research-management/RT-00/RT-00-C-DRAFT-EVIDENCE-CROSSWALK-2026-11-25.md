# RT-00 C — Draft proposal evidence crosswalk

**Date:** 2026-11-25  
**Baseline:** `b482dc4415730c16518adeac54b94a8982021a3d` (`main`)  
**Scope:** the complete current `draft/` set: README, accepted architecture decision, glossary, and examples.  
**Status:** traceability crosswalk completed; linked research remains scoped/proposal-level where stated.

## Question and method

Does each existing non-normative glossary proposal and accepted architecture boundary point readers to research that addresses its subject, and do those links preserve the research's status? I enumerated proposal/accepted-decision sections in the draft files, followed the current linked RT/Scenario sources, and checked their stated scope and status. This audit does not validate the language semantics or decide whether a proposal should be adopted.

## Crosswalk

| Draft section | Supporting research | Relationship and limit |
| --- | --- | --- |
| Accepted immutable-component and single-toolchain decision | [RT-20 identity/compatibility](../toolchain-and-collaboration/RT-20/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md); [Scenarios 109–111](../README.md#core-semantic-and-type-research); [Scenario 134](../packages-and-ecosystem/RT-18/RESEARCH-SCENARIO-134-WIRE-SCHEMA-EVOLUTION-INTEROPERABILITY.md); the [public-interface proposal](../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md) explicitly respects the decision | The existing `Related` links and proposal's decision link cover the call-compatibility, finite wire-format, prior-art, and immutability boundaries. Scenario 134 is prior-art-only under the decision. These links trace the accepted rationale; they do not replace a maintainer record or prove every language-level consequence. |
| Structural/type identity, representation, layout, and C ABI terms | [RT-09 structural identity and ABI proposal](../compiler-and-translation/RT-09/RT-09-STRUCTURAL-TYPE-IDENTITY-LAYOUT-AND-C-ABI-PROPOSAL.md); [Scenario 70](../language-design/RT-04/RESEARCH-SCENARIO-70-TYPE-ALIASES-NEWTYPE-AND-OPAQUE-ABSTRACTIONS.md); [Scenario 72](../compiler-and-translation/RT-13/RESEARCH-SCENARIO-72-SUM-TYPE-LAYOUT-ABI-AND-INTEROPERABILITY.md) | Direct topic support is now linked from the glossary. RT-09 is explicitly a proposal; the bounded prior studies do not establish canonical hashes or a production ABI. |
| Contract, Operation, implementation, conformance class, and evidence terms | [RT-20 Contract Identity and Compatibility](../toolchain-and-collaboration/RT-20/RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md); [Scenario 10](../packages-and-ecosystem/RT-12/RESEARCH-SCENARIO-10-CONTRACT-IMPLEMENTATION-BINDINGS.md); [Scenario 14](../language-design/RT-02/RESEARCH-SCENARIO-14-FORMAL-BEHAVIORAL-CONTRACTS-AND-REFINEMENT.md) | RT-20 explicitly separates exact Contract-object identity from `OpHash`, `CCHash`, `ImplHash`, and behavioral refinement. The mapping from call-site required/provided contracts to conformance-class membership remains open. |
| Public interface extension | [RT-05 Public Interfaces and Contract Refinement](../semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md); [receipt-rebind pilot](../semantic-representation/RT-05/PUBLIC-INTERFACE-VERIFICATION-REBIND-2026-11-24.md) | The first is an unadopted model proposal; the pilot is a bounded evidence example and does not prove general source-to-provider conformance. |
| Assumption, authorization, conditional proof, discharge, and closure terms | [RT-36 Formal Verification Assumptions and Trust](../formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md) | The glossary link is direct. The runtime issuer, authorization policy, and production trust boundary remain open. |

The examples README is guidance for illustrative programs, not a semantic proposal; its instruction not to claim testing/proof without execution is consistent with the repository's evidence rules. No example implies a new core-language guarantee.

## Result and disposition

The previous links were concentrated in the public-interface, RT-20, and assumption sections; the early type/layout/ABI glossary terms lacked a direct research crosswalk. Added a section-level, explicitly non-normative map near the glossary introduction. This is the smallest traceability structure that covers the current proposal families without presenting proposal documents as validation.

The plan's existing “research remains exploratory / draft remains candidate specification” boundary is preserved. A citation proves discoverability, not correctness or acceptance. The underlying research still leaves canonical type/ABI identity, operation/class mapping, general provider refinement, and production proof/assumption policy open. Independent technical review and maintainer approval remain external gates.

## Reproduction

At the pinned baseline, enumerate `draft/*.md` and `draft/examples/*.md`; inspect headings/status labels and follow each relative `research/` link. Verify target existence with the repository's offline Markdown link/anchor workflow. The machine-readable record stores the paths and evidence status for each crosswalk row.
