# RT-00 B — Compare the English and Russian concept proof boundaries

## Question and source

Does the known Russian concept lag change the meaning of the concepts shared by both documents, especially the distinction between a checked proof and assurance about executable code? I reviewed the English and Russian §18A texts clause by clause at `12a780a6e3d864eb7c377e631b0de12b12ebbbd2` on `research/all`. I compared each clause's subject, obligation strength, premises, scope and consequence, then checked the English-only extension against RT-36. This refines the [earlier document-level finding](RT-00-B-12-TEXT-OVERLAP-2026-11-24.md), which located the omitted section through scope review. A heading comparison locates omissions, while this study also reads the shared clauses. The table carries the section mapping and scope without a separate diagram. [English concept](../../language-design/RT-01/LLMLang-CONCEPT.md#18a-unified-semantics-and-automated-formal-verification) · [Russian concept](../../language-design/RT-01/LLMLang-CONCEPT.ru.md) · [RT-36](../../formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md)

## Findings

| Section | Shared semantics and wording differences |
|---|---|
| §18A.1 | Both derive execution and verification from one canonical representation and permit explicitly linked auxiliary lemmas, invariants, abstractions and assumptions. English describes freedom from having to rewrite an algorithm in TLA+. The Russian use of `не должен` can also read as an instruction against rewriting. The following clauses in both versions reject a second independent description of executable logic and allow linked proof material. |
| §18A.2–3 | Both require formal semantics for every construct in the supported core, scope each backend's preservation obligation and allow an explicitly distinguished limited extension. Both use `SHOULD` for automatic model generation within backend support and distinguish bounded model checking from unbounded proof. |
| §18A.4 | Both separate a declared guarantee, implementation conformance and other implementation properties. Both retain the relevant assumption for a caller proof, assign status by property and propagate evidence through the actual property dependencies. English opens with a recommendation for compositional verification, while the Russian wording reads as a requirement. The applicable conditions for using a callee's contract agree. |
| §18A.5 | Both require an argument for each transformation from the same source semantics and allow explicit refinement for a backend with extra internal states. Both propose independent translation validation as an initial approach. |
| §18A.6 | Both define the same five statuses and explicitly scope `PROVEN` to a checked proof under the assumptions for the named property. A runtime check or finite-state check has a distinct result type in both. |
| §18A.7–8 | Both bind artifacts to source content identities, semantics, backend, configuration and assumptions. Both require invalidation of affected results and a documented trust chain that scopes guarantees about executable code. |
| §18A.9 | Present in English only. It introduces RT-36 as a research proposal. It names typed assumptions, exact foreign-provider bindings, authorization, dependency closure, discharge and revocation, and separate proof outcome, closure, freshness and admission. |

The scoped comparison found no direct conflict between the two documents' shared proof-status or trust obligations. The two wording differences affect the apparent strength of design requirements. The omitted English §18A.9 adds proposed machinery and sharper terminology. It leaves the existing meaning of `PROVEN` in §18A.6 in place. Russian §18A.4 and §18A.6 already retain open assumptions and property scope. They supply the existing conceptual boundary, while RT-36 is the source for the proposed identity, authorization and lifecycle model. [RT-36 candidate status dimensions](../../formal-verification/RT-36/RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md#4-candidate-status-dimensions)

For LLMLang synthesis, this comparison identifies terminology whose obligation strength needs deliberate alignment and a candidate extension that an equal version label cannot establish as translated. The two concept documents remain complementary research materials. This audit covers §18A, leaving translation parity outside that section and independent language review open. [Corpus reconciliation](https://github.com/aivibeflow/LLMLang/issues/284) · [RT-36 issue](https://github.com/aivibeflow/LLMLang/issues/436)

## Source verification

The English blob is `2f592de203f5ae38529b8e539f79bf9279b5f1dd`, with §18A on lines 858–946. The Russian blob is `afa27041670e0d295bd7e0d9d0a3c96c2c584d62`, with §18A on lines 859–944. Use these commands to locate the exact texts. Classifying the claims requires the manual reading above.

```bash
dir=research/language-design/RT-01
for file in LLMLang-CONCEPT.md LLMLang-CONCEPT.ru.md; do
  git rev-parse "12a780a:$dir/$file"
  git show "12a780a:$dir/$file" | sed -n '/^## 18A\./,/^## 19\./p'
done
```
