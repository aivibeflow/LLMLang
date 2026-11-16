# Research Scenario 29 — Verified SMT Proof Checking and Encoder Validation

**Status:** Research proposal / prototype design. Not a normative LLMLang decision.  
**Date:** 2026-11-17  
**Depends on:** Scenarios 25–28, especially the symbolic relational verifier and the proof boundary.  
**Question:** Can a solver-reported UNSAT result become a LLMLang proof status only after an independently checked certificate establishes unsatisfiability of the exact relational query generated from the canonical program IR?

## 1. Executive conclusion

The strongest currently identified candidate is **Logos**, the Lean-based proof checker for cvc5's Cooperating Proof Calculus (CPC).

Logos is a substantially stronger fit than treating a solver's UNSAT response as a proof, or relying only on an unverified external checker:
- its checker soundness theorem is proved in Lean;
- its proof rules are generated from the CPC calculus and have Lean correctness proofs;
- its executable reports `correct`, `incorrect`, or `incomplete`;
- a `correct` verdict is connected by a Lean theorem to unsatisfiability of the assumptions the proof parser extracted.

However, Logos is **not a drop-in proof boundary** for LLMLang. Three obligations must be addressed before its result can be used as `PROVEN`:

1. **Bind the parsed assumptions to the exact LLMLang query.** Logos explicitly does not compare proof assumptions against the original solver input, and its s-expression parser is outside the correctness theorem.
2. **Stay inside a semantics fragment that agrees with SMT-LIB.** The initial profile should be quantifier-free linear integer arithmetic (QF_LIA), with no arrays, uninterpreted sorts, user functions, nonlinear multiplication, strings, or quantifiers.
3. **Prove the LLMLang-to-query translation.** A checked proof of the generated formula does not by itself prove that the formula correctly represents the source program's paired executions.

The intended architecture is therefore:

```text
Canonical typed program IR
        |
        v
Relational Query IR
        |
        +----------------------+
        |                      |
        v                      v
SMT-LIB QF_LIA text      Expected Logos Term AST
        |                      |
        v                      |
cvc5 CPC proof                 |
        |                      |
        v                      v
CPC proof parser ----> exact assumption-list equality
        |                      |
        +----------+-----------+
                   |
                   v
       Logos CPC proof checker
                   |
                   v
     Lean theorem for expected query
                   |
                   v
     PROVEN_INDEPENDENCE (QF_LIA)
```

The source-to-query and query-to-Logos-term correspondence must itself be established. Until then, the checker result is evidence about a formula, not a proof about the LLMLang source program.

## 2. Candidate checker research

### 2.1 Logos — preferred primary checker

Repository: https://github.com/cvc5/logos  
Pinned research revision: `cf18742973861b3718d04c5f25775448098ff474`  
Lean toolchain: `leanprover/lean4:v4.34.0`  
Verification project's Mathlib dependency: `v4.34.0`

Logos checks cvc5 CPC proof certificates. Its central theorem, `correct___eo_is_refutation`, states that a successfully checked CPC derivation establishes unsatisfiability of its assumption list under the semantics formalized in `Cpc/SmtModel.lean`. The executable-level theorem `correct___logos_check_proof` connects this result to the text accepted by the proof parser.

The proof checker is a separate Lean implementation from cvc5. The proof rules are generated from the CPC definition, but the soundness of those rules is established by Lean proofs. This removes cvc5's solver implementation from the trusted basis for an accepted UNSAT result.

Logos's verdicts have different meanings:
- `correct`: the parsed assumptions are unsatisfiable under the semantics covered by the theorem;
- `incorrect`: the parsed commands do not form an accepted refutation;
- `incomplete`: the proof is accepted as a CPC derivation, but a translation side condition required by the soundness theorem fails;
- parser/build/process errors: no proof result.

Only `correct`, together with the additional LLMLang binding obligations below, can be promoted to a proof status. `incorrect`, `incomplete`, missing checker, timeout, or parser error must fail closed to `UNKNOWN`.

### 2.2 Why not Ethos alone?

Ethos checks proof steps against an Eunoia signature. This is useful for checking the mechanics of CPC derivations, but Ethos's C++ checker does not itself provide the same Lean theorem that Logos provides. A formalized rule signature is not equivalent to a machine-checked proof that the executable checker is sound.

Ethos can remain a useful secondary diagnostic or performance comparison. It must not be the sole source of LLMLang's `PROVEN` status.

### 2.3 Why not Carcara as the primary checker?

Carcara is a high-performance Rust checker for Alethe proofs. Its verdicts distinguish `valid`, `invalid`, and `holey`; a holey proof contains an explicit hole or an unsupported rule and must not be treated as checked.

Carcara is an independent implementation, but it is not formally verified. It is useful as a secondary cross-check and as an alternative proof-format experiment. Logos is the stronger primary candidate because its checker soundness is proved in Lean.

## 3. Critical proof boundary: bind assumptions to the intended query

Logos documents an important limitation: the parser and s-expression reader are unverified, and the executable does not compare the assumptions parsed from the proof file against the original SMT-LIB input problem. The theorem is about the assumptions the parser returned.

This is not acceptable as the complete LLMLang boundary. A proof of a different formula is irrelevant even if that proof is perfectly checked.

### 3.1 Required wrapper

Add a small Lean wrapper around the Logos API. Its inputs are:
- the CPC proof text or proof artifact;
- the expected assumption list, constructed from the canonical Relational Query IR by the LLMLang translator.

The wrapper must:
1. call the Logos CPC parser;
2. reject parser errors;
3. obtain `(parsedAssumptions, parsedCommands)`;
4. compare `parsedAssumptions` with `expectedAssumptions` by exact structural equality of the Lean `Term` ASTs;
5. reject any mismatch;
6. run the existing Logos verdict/checker on the parsed commands and the matched expected assumptions;
7. return `correct` only if all existing checker and translation side conditions pass.

The wrapper must have its own Lean theorem. Its intended shape is:

```lean
theorem correct_expected_query
    (proofText : String)
    (expectedAssumptions : List Term)
    (parsedAssumptions : List Term)
    (commands : CCmdList)
    (hParse : parseProof proofText = Except.ok (parsedAssumptions, commands))
    (hSame : parsedAssumptions = expectedAssumptions)
    (hCorrect : logos_verdict parsedAssumptions commands = Verdict.correct) :
    eo_satisfiability
      (logos_assumption_term expectedAssumptions) false := by
  -- derive from correct___logos_verdict and hSame
```

This is a design sketch, not compiled Lean code.

The key point is that the parser's output assumptions are not trusted merely because the parser produced them. They must be structurally identical to the independently generated expected assumptions.

The CPC command parser remains unverified. That does not by itself invalidate the soundness result: the checker verifies every parsed command as a CPC derivation, and the Lean theorem establishes that any accepted derivation from the bound assumptions proves false. If the parser changes the command stream but the resulting stream is still accepted, it has still supplied a valid derivation. The critical condition is that it cannot silently change the assumptions being proved.

A separate parser that compares text or hashes outside the Lean wrapper is insufficient. The equality check must compare the ASTs used by the theorem inside the trusted Lean wrapper.

### 3.2 One assertion per proof query

The first integration should generate exactly one SMT-LIB `assert` containing the complete relational counterexample formula. The wrapper should require the proof's assumption list to contain exactly the expected formula (or an explicitly specified, structurally identical list).

Do not introduce permissive algebraic normalization at this stage. A syntactic mismatch should reject the certificate. If cvc5 normalizes the assumption into a different shape, add only a separately proved equivalence/canonicalization rule; do not silently accept a string-level similarity.

## 4. Restrict the initial semantic profile to QF_LIA

Logos's formal semantics is not identical to every part of SMT-LIB:
- arrays are modeled as almost-constant maps, which can matter for quantified formulas;
- uninterpreted-sort cardinality is restricted;
- higher-order function values are not given the standard SMT-LIB 2.7 extensional semantics;
- there are extensions and lenient typing cases outside the standard.

The conformance document states that the relevant narrowing differences require quantifiers to become observable; on quantifier-free linear fragments the semantics agrees with SMT-LIB. The initial LLMLang proof profile should stay strictly inside that fragment.

### 4.1 Allowed in the first profile

- `Bool` and `Int`;
- Boolean constants, variables, `not`, `and`, `or`;
- integer constants and variables;
- `+` and `-`;
- multiplication only when at least one operand is an integer literal/constant;
- `=`, `<`, `<=`;
- `ite` with a Boolean condition and same-sort branches;
- pure functions only after inlining into the supported expression fragment;
- explicit paired inputs, explicit initial state, and an explicit observable-state boundary.

### 4.2 Rejected in the first profile

- quantifiers;
- arrays, sequences, sets, datatypes, and uninterpreted sorts;
- user-declared uninterpreted functions;
- function values, higher-order terms, and partial application;
- `Real`;
- nonlinear multiplication (variable multiplied by variable);
- division, modulo, and any partial/underspecified arithmetic operator;
- strings and regular expressions;
- events, exceptions, nondeterminism, concurrency, aliasing, or external calls;
- any term whose SMT-LIB typing is not independently validated.

The current symbolic encoder is broader: it accepts `String` and multiplication of arbitrary integer expressions, and emits `(set-logic ALL)`. It must **not** be reused unchanged for the Logos proof profile. Add a separate QF_LIA validator/encoder and emit an explicit `(set-logic QF_LIA)`.

The current Scenario 26 evaluator uses mathematical integer arithmetic, which is compatible with the integer arithmetic model required here. Machine overflow semantics must not be silently introduced into this profile.

## 5. Relational query being proved

For a program `P), input factor `p`, and observable tuple `Obs`, create two symbolic executions:

- left and right inputs are equal for every factor except `p`;
- `p_L != p_R`;
- the initial state and initial locals are identical;
- the observation boundary is identical.

The counterexample formula is:

[
Delta_p land
left(
  Delta_{mathrm{return}}
  lor igvee_{s in VisibleState} Delta_s
ight)
]

where each `Delta` is inequality between the corresponding left and right observations.

All free variables are declared as SMT-LIB constants. Satisfiability therefore asks whether a counterexample assignment exists.

- SAT gives a concrete candidate pair. Replay it against the exact reference evaluator and initial environment. A successful replay yields a confirmed dependency witness.
- UNSAT proves that no counterexample exists in the encoded domain. If the CPC proof is accepted by Logos, the assumptions are bound to the expected query, and the query translation is proven correct, the factor is independent for the stated observation boundary.

The proof must cover the disjunction of all selected observable components, not merely one convenient output. If one output differs, the factor is a dependency.

## 6. End-to-end pipeline

### 6.1 Canonical query generation

The canonical Relational Query IR is the only source for both:
- SMT-LIB QF_LIA text sent to cvc5;
- expected Logos `Term` AST passed to the Lean wrapper.

The IR identity must include:
- typed program IR digest;
- semantic/evaluator version;
- factor under analysis;
- exact input declarations and domains/sorts;
- initial state and initial locals;
- observable-state selection;
- query-construction version;
- QF_LIA profile version.

The SMT-LIB printer and Logos-Term compiler must be deterministic.

### 6.2 Solver proof production

Candidate cvc5 version: **1.4.2**  
Release tag commit: `282d5e0c84baf49c780704c532f87ba66d8b513d`

Candidate command:

```bash
cvc5 \
  --dump-proofs \
  --proof-format-mode=cpc \
  --proof-granularity=dsl-rewrite \
  query.smt2 > proof.cpc
```

The exact cvc5 binary hash, version, command, options, query bytes, and proof bytes must be recorded. A solver-reported `unsat` without a proof artifact is not proof evidence.

The candidate compatibility pair is cvc5 1.4.2 plus Logos commit `cf18742973861b3718d04c5f25775448098ff474`. This pair has **not** been executed together in the current environment; a golden proof integration test is mandatory before pinning it as a supported toolchain.

### 6.3 Logos proof verification

Candidate Logos revision: `cf18742973861b3718d04c5f25775448098ff474`  
Lean toolchain: `leanprover/lean4:v4.34.0`  
Verification Mathlib: `v4.34.0`

Required build validation:
1. run the checker-boundary build;
2. run the proof-hygiene check;
3. run the representative CI checks;
4. build every CPC rule proof with `scripts/build-all-cpc-rules.sh`;
5. build `Cpc.ApiCorrect` with `scripts/build.sh Cpc.ApiCorrect`;
6. retain the exact commit, Lean/Mathlib versions, build logs, and executable hash.

The full per-rule proof build takes more than two hours and is not fully performed by upstream CI. A partial CI pass or textual absence of `sorry` is not a substitute for the full proof build. No LLMLang `PROVEN` result should rely on a checker revision whose complete proof build has not been validated for the release.

### 6.4 Status mapping

| Condition | LLMLang status |
| --- | --- |
| Solver says UNSAT, no certificate | `SOLVER_REPORTED_UNSAT` |
| Logos says `correct`, but parsed assumptions do not exactly equal expected assumptions | `UNKNOWN` |
| Logos says `incorrect`, `incomplete`, parser error, timeout, or missing checker | `UNKNOWN` |
| Checker/build/toolchain identity is not pinned or full proof build is not validated | `UNKNOWN` |
| Query is outside QF_LIA or fails the linearity/type validator | `UNSUPPORTED` / `UNKNOWN` |
| Logos theorem applies, assumptions match, query translation is proven, and full checker build is validated | `PROVEN_INDEPENDENCE` |
| SAT witness successfully replays against the exact reference evaluator | `CONFIRMED_DEPENDENCY_WITNESS` |

A `correct` verdict alone is not sufficient for `PROVEN_INDEPENDENCE`. The LLMLang translation theorem and exact assumption binding are mandatory.

## 7. Proof and evidence identity

A proof evidence record must bind the complete dependency closure:

- source program IR digest;
- typed IR digest and semantics version;
- relational query IR digest and query-builder version;
- SMT-LIB query digest and exact query bytes;
- expected Logos assumption AST digest;
- parsed assumption AST digest and structural equality result;
- CPC proof digest and exact proof bytes;
- cvc5 version, source commit, binary SHA-256, command, and options;
- Logos source commit, Lean toolchain, Mathlib revision, full proof-build receipt, and executable SHA-256;
- wrapper source digest and theorem/build identity;
- QF_LIA profile version and observation contract;
- final verdict and the exact inputs to which it applies.

Any change to the source IR, query, encoder, semantics, observation boundary, solver/checker binary, proof, or wrapper invalidates the evidence unless a sound reuse rule proves otherwise.

The proof record must be created by the trusted verification runner after it invokes the pinned tools. A user-supplied JSON object that merely claims `correct` must never promote itself to `PROVEN`.

## 8. Encoder validation obligations

This scenario has two separate correctness targets.

### 8.1 Relational formula correctness

Prove that the generated formula is satisfiable exactly when there exists a pair of legal input assignments:
- equal on every factor except the selected factor;
- different on that factor;
- producing different values in the declared observation tuple.

This is the logical definition of dependency, not a heuristic.

### 8.2 Program-to-query correspondence

Prove that the left and right symbolic executions in the relational query correspond to executions of the same typed program IR under the declared semantics.

The first prototype can use the existing finite evaluator as a differential oracle over small finite subsets. This is useful for finding encoder bugs, but it is not a proof of the unbounded QF_LIA translation.

The long-term result should be a Lean theorem over the restricted AST, not a claim based only on tests. The theorem must account for:
- variable environments and explicit state regions;
- pure function inlining;
- conditional branches and `ite` encoding;
- integer arithmetic and linearity restrictions;
- return and selected-state observations;
- exact initial locals and initial state.

Until this theorem exists, a checked Logos proof establishes unsatisfiability of the generated formula only. It does not establish the source-level dependency property.

## 9. Adversarial acceptance tests

The integration must include at least these cases:

1. A valid UNSAT QF_LIA proof is accepted and bound to the exact expected assumption AST.
2. A proof for a different query is rejected even if Logos reports `correct` for that proof.
3. An altered query with the old proof is rejected.
4. An altered proof with the old query is rejected.
5. A truncated proof, missing premise, wrong premise index, or corrupted final step is rejected.
6. A CPC proof containing a trust/unsupported step cannot yield `PROVEN`.
7. A Logos `incomplete` verdict cannot yield `PROVEN`.
8. A parser error cannot yield `PROVEN`.
9. A solver UNSAT response without a proof cannot yield `PROVEN`.
10. A checker executable with a different hash or unvalidated build cannot yield `PROVEN`.
11. A proof generated for one initial state cannot be reused for another.
12. A proof generated for one observation boundary cannot be reused for another.
13. A nonlinear multiplication expression is rejected by the QF_LIA validator.
14. SAT witnesses are replayed; a malformed, incomplete, or non-reproducing witness is not confirmed.
15. The finite evaluator and QF_LIA encoder agree on generated finite test cases, while the report explicitly distinguishes testing from proof.

## 10. What is not established by this scenario yet

- No cvc5/Logos integration has been executed.
- No Logos proof build has been run in the LLMLang environment.
- No proof certificate has been generated or checked.
- No Lean wrapper theorem has been implemented or compiled.
- No proof of the LLMLang relational encoder has been established.
- No source-to-native-code or compiler/runtime correspondence has been established.

These are explicit open obligations, not assumed successes.

## 11. Research references

1. Logos verified checker, correctness theorem, parser boundary, and full-build requirements:  
   https://github.com/cvc5/logos/tree/cf18742973861b3718d04c5f25775448098ff474
2. Logos executable correctness theorem:  
   https://github.com/cvc5/logos/blob/cf18742973861b3718d04c5f25775448098ff474/Cpc/ApiCorrect.lean
3. Logos SMT-LIB conformance limitations:  
   https://github.com/cvc5/logos/blob/cf18742973861b3718d04c5f25775448098ff474/docs/smt-lib-conformance.md
4. Logos parser boundary:  
   https://github.com/cvc5/logos/blob/cf18742973861b3718d04c5f25775448098ff474/docs/parser.md
5. Logos native proof interface and its unchecked script-shape limitation:  
   https://github.com/cvc5/logos/blob/cf18742973861b3718d04c5f25775448098ff474/docs/lean-native-proofs.md
6. cvc5 1.4.2 CPC proof format and proof-generation options:  
   https://cvc5.github.io/docs/cvc5-1.4.2/proofs/output_cpc.html
7. cvc5 1.4.2 release:  
   https://github.com/cvc5/cvc5/releases/tag/cvc5-1.4.2
8. Ethos proof checker:  
   https://github.com/cvc5/ethos
9. Carcara proof-checking outcomes (`valid`, `invalid`, `holey`):  
   https://ufmg-smite.github.io/carcara/checking.html
10. The Cooperating Proof Calculus: Comprehensive Proofs for an SMT Solver, CAV 2026:  
    https://doi.org/10.1007/978-3-032-32526-6_9

## 12. Next implementation sequence

1. Create a tiny canonical `RelationalQueryIR` for one integer input and one integer return value.
2. Implement a QF_LIA-only validator; reject nonlinear operations and unsupported constructs.
3. Generate both SMT-LIB text and expected Logos `Term` AST from the same canonical query IR.
4. Implement the Lean wrapper with exact assumption-list equality and a theorem for the expected query.
5. Pin and build cvc5 1.4.2 and Logos at the commits above; verify compatibility with a golden proof.
6. Run valid, corrupted, mismatched-assumption, incomplete, and unsupported-rule tests.
7. Prove the relational-query and program-to-query correspondence in Lean.
8. Only then allow a Logos-checked result to become `PROVEN_INDEPENDENCE`.

No normative LLMLang document is changed by this research proposal.
