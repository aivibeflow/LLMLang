# RT-05 — Typed Semantic Program Graph

- **Status** · Candidate model and executable experiment
- **Date** · 2026-11-21
- **Plan** · §1.1, Semantic Program Graph and program representation
- **Baseline** · `1b292c9a6b18cf64df87e0b1f43d70ad3a648194` plus the study files linked below

## 1. Research question

Can a typed graph give two source representations the same canonical value, preserve distinctions that affect execution, and retain enough structure to track changes across Specification, Design, and Implementation? §1.1 shares the plan's highest complexity rating with synchronized semantic merge (§4.5) and human/agent evaluation (§7.5). Representation comes first in the plan's dependency order and supplies an input to semantic merge. [Research plan](../PLAN.md#11-semantic-program-graph-and-program-representation)

The experiment uses a closed scalar fragment with ordered event traces and two call modes. The candidate model also covers requirements, resource ownership, evidence, and artifact granularity. Those parts of the model draw on prior studies and have separate validation gates. [RT-03/04 shared corpus](RT-03-04-SHARED-SEMANTICS-CORPUS.md) · [COR-13 ownership across calls](RESEARCH-COR-13-TYPED-OWNERSHIP-ACROSS-CALLS.md)

## 2. Prior evidence

- The concept establishes three optional logical layers. The dependency index extracts dependencies from a narrow declaration envelope. Its input already declares references, leaving source lowering and independent completeness evidence open. [LLMLang concept, §§3–4](LLMLang-CONCEPT.md#3-модель-программы-semantic-program-graph) · [RT-24 reconciliation, §5](RT-24-IDENTITY-AND-SPG-RECONCILIATION.md#5-reconciliation-with-the-existing-executable-spg-subset)
- Roslyn's full-fidelity syntax tree retains source tokens, trivia, and malformed nodes. LLVM specifies equivalent in-memory, bitcode, and assembly representations of its own IR. Together they motivate keeping a lossless editing representation alongside a resolved representation with its own structural equality. [Roslyn syntax model](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/work-with-syntax#syntax-trees) · [LLVM Language Reference](https://llvm.org/docs/LangRef.html#abstract)
- Unison addresses a mutually recursive definition by cycle hash and member position. The existing RT-05 prototype compares keyed and structural group encodings. This study reuses those encodings and checks whether stored typed bodies still execute through both. [Unison literal hash references](https://www.unison-lang.org/docs/language-reference/literal-hash-references/) · [RT-05 recursive identity](RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md)
- RFC 8785 sorts object properties and preserves array order. A semantic schema must additionally determine whether a collection represents a sequence, set, or map before encoding. The fixture uses the existing store's restricted Python JSON encoding. [RFC 8785, §3.2.3](https://www.rfc-editor.org/rfc/rfc8785.html#section-3.2.3) · [Content Store implementation](PROTOTYPES/DEPENDENCY-GRAPH-01/src/semantic_graph.py)

## 3. Candidate graph model

For a fixed semantic profile `P`, an SPG state comprises immutable typed values `V`, typed exact edges `H`, and snapshot selections `S`. `S` identifies available roots and the exact bindings used in that snapshot. Provenance, structural ownership of managed occurrences, conformance claims, and lineage can be expressed as scoped relations `R` linked to exact endpoints. A relation enters `H` where the meaning of its source depends on the exact target. Each relation kind needs a source kind, a target kind, a cardinality, an order policy, and a rule for resolution. The hash dependency graph is the projection of `H` after grouping supported cycles.

| View | Nodes and relationships | Version boundary |
|---|---|---|
| Specification | Accepted obligations, invariants, contracts, and observation models. Contracts can refer to exact types or semantic assumptions. Requirements can trace to several contracts. | A contract version changes with its semantic payload or exact dependencies. Clarification and approval history attach to exact versions. |
| Design | Operations, interfaces, component boundaries, allowed dependencies, and behavioral constraints. An operation references its exact interface and contract. | A design rule used to admit or interpret a program is an explicit semantic input. An advisory rationale can be a scoped relation. |
| Implementation | Typed bodies and exact dependencies, including calls. A body may declare which design operation it provides. A binding selects a concrete implementation for an exact operation. | Pin the implementation for a concrete call. Pin the operation in a call that delegates provider choice and pin the selected implementation in the execution context. |

The views can share type values. A design-to-specification `refines` relation and an implementation-to-design `provides` relation name exact endpoints. Their structural validity establishes what is claimed. A verifier establishes the corresponding behavioral judgment under explicit assumptions. An implementation-only project can have an empty requirement set. A project's required verification and review rules determine which views and judgments must be present. [Concept, §4](LLMLang-CONCEPT.md#4-три-логических-слоя-программы) · [Contract identity and compatibility](RT-20-CONTRACT-IDENTITY-AND-COMPATIBILITY.md)

**Containment and references.** A managed declaration can occupy a unique slot within an owning scope, while arbitrarily many slots and typed references can share the same immutable value. A scope move preserves a value if the resolved inputs, visibility, and outward interface are preserved. Access, nominal type identity, capability constraints, and runtime resource ownership enter the typed semantics when they affect admission or observations. For example, an owned return and a borrowed return must retain their distinct obligations even if they have the same runtime pointer representation. [Type aliases and nominal types](RESEARCH-SCENARIO-70-TYPE-ALIASES-NEWTYPE-AND-OPAQUE-ABSTRACTIONS.md) · [Typed caller recovery](RESEARCH-SCENARIO-132-TYPED-CALLER-RECOVERY.md)

**Import boundary.** A source inventory and pinned language/profile and external dependencies determine what gets parsed and resolved. A lossless source view supports editing and diagnostics. Lowering maps its resolved syntax to typed graph values and can record source spans in `R`. Generated code and binaries link back to exact action inputs, including their semantic subject, backend, target, and options. Source correspondence for those outputs requires its own tests or proof. The prototype takes explicit in-memory declaration maps and lowers two textual body syntaxes. Repository-wide source inventory, module resolution, and RT-06 completeness are separate open requirements. [RT-24, §4](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md#4-repository-representation-contract) · [LLVM preservation evidence](RESEARCH-SCENARIO-96-LLVM-UB-POISON-AND-SEMANTIC-PRESERVATION.md)

## 4. Canonicalization and executable model

| Input | Candidate rule in the experiment |
|---|---|
| Local parameter names, comments, parentheses with the same parse, integer token spelling | Resolve a local binding to its parameter position, then retain the typed literal or operation. The two frontends use a restricted Python expression AST and a JSON prefix grammar. |
| Type, exported label, declared contract | Preserve exact typed distinctions. The interface holds ordered parameter type references and one result type. The operation points to its exact interface and contract. |
| Sequence of operands and effects | Preserve order and multiplicity. `emit` records its label before its continuation. `if` evaluates one arm. Arithmetic and arguments evaluate left to right. |
| Contract with several permitted event traces | Canonicalize the outer collection as a set. Preserve each inner sequence, including repeated labels. The empty event trace is one possible trace. |
| Calls | Preserve the distinction between an operation reference and a concrete implementation pin. Keep a reference position for each occurrence in the typed body template. |
| Inventory, locations, and evidence | Order selections deterministically. Keep path and observation records outside the value preimage. Explicit selection keys participate in fixture snapshot identity. |

For example, `emit("seen", n + 0x2)` and `["emit", "seen", ["add", ["arg", "input"], 2]]` lower to the same body when their interfaces and other exact inputs coincide. A local parameter is typed by its enclosing interface. Integer literals are signed 32-bit values in the fixture grammar, while evaluation uses mathematical integer arithmetic through Python integers. The remaining terms are Booleans, arguments, integer addition, subtraction and equality, conditional selection, event emission, and calls. Success produces a typed result and an ordered event tuple. The call budget counts entry and nested calls, with exhaustion reported separately. [Prototype implementation](PROTOTYPES/DEPENDENCY-GRAPH-01/src/spg_representation.py)

The normalization hypothesis is that positional parameter resolution and the listed syntactic rewrites preserve the stored body and its observations in a fixed context. A differing graph encoding or differing trace under either frontend would falsify it. The contrasting hypothesis that equality can be obtained by sorting observable operands or discarding event repetitions predicts identical canonical forms for pairs the trace model distinguishes. A third hypothesis, that caller value identity suffices as an execution cache input, predicts equal observations after a binding-only update. The controls in §7 exercise all three.

The canonical body is a versioned typed template with an ordered reference vector. Encoding uses the existing Content Store's deterministic UTF-8 JSON and SHA-256, with fixture kind/version markers. The snapshot selects contract, operation, implementation, and binding values. Interfaces and scalar types appear as reachable values. Graph encoding round-trips through existing persistence for graphs produced by the fixture compiler. The standard wire schema, cross-language bytes, profile negotiation, and distinct `OpHash`, `ImplHash`, `CCHash`, and evidence envelopes are open. [Draft glossary](../draft/GLOSSARY.md) · [LL-004](../TODO.md#ll-004--choose-canonical-encoding-and-hash-algorithm-policy)

### Recursive structures

Construct strongly connected components from exact implementation pins. Encode internal references as local positions, commit ordered member bodies and external addresses to the group, and resolve published members through the group address. Condensation orders the groups by exact external dependencies. A group edit can change the addresses used by all its members and their exact callers. Operation-dispatched calls can form runtime cycles through the binding snapshot independently of the exact hash graph. Admission of recursive types needs separate rules for binding, visibility, and type equality. [RT-05 recursive identity](RT-05-RECURSIVE-IDENTITY-EXPERIMENT.md) · [Scenario 36](RESEARCH-SCENARIO-36-RECURSION-TERMINATION-AND-FUEL.md)

| Encoding | What it buys | Cost and decision gate |
|---|---|---|
| DAG-only publication | Simple addressing order for acyclic exact references | Rejects exact recursive edges. Useful as an explicitly restricted profile. |
| SCCs ordered by explicit member keys | Separate member addresses even for symmetric members | Key allocation can change addresses. Decide whether keys are semantic or belong only to managed occurrences. |
| Structurally canonical SCCs | Stable addresses across display renames and shared values for symmetric members | The fixture searches permutations and caps components at six members. Independently governed occurrences still need selectors. A scalable canonicalizer and larger recursive workloads are open. |

## 5. Evolution and continuity

| Change | Candidate record |
|---|---|
| Edit a continuing item | Create a new immutable value if meaning changes. Pin the old and new selections and record continuation under the selected identity policy. Keep existing exact references until a caller or binding explicitly changes. |
| Replace or delete | End the old selection. Replacement adds a fresh managed lifetime. Record any asserted `supersedes` relation independently of continuation. A recreated equal value can reuse storage. |
| Split or merge managed items | Declare one-to-many or many-to-one lineage over exact endpoint selections. Classify the callers and contract obligations independently for every edited use. |
| Move or copy | Move records continuity with appropriate scope evidence. Copy allocates a separate managed selection where independent evolution is required. Resolve both sides before deciding whether values can be shared. |

Lineage endpoints should include a causal revision identity and the selected value and slot expected there. Equal states can recur after deletion and recreation. The reused prototype checks a pair of fixture state digests, including aliases, and validates endpoint membership and cardinality. Causal ancestry and authority to assert lineage require further evidence. The call reference positions used by the representation describe structure in one body version. Tracking a call across extraction, duplication, or reordering requires RT-20's separate occurrence and obligation rules. [RT-05 lifecycle experiment](RT-05-IDENTITY-LIFECYCLE-EXPERIMENT.md) · [Call-site refactoring experiment](RT-05-RT-20-CALL-SITE-REFACTOR-EXPERIMENT.md)

Stable entity IDs, scoped lifetime slots, and explicit lineage remain compatible candidates for the managed layer. Stable IDs provide direct matching across scope moves and need allocation and import rules. Scoped slots simplify local matching and need explicit moves and lifetime checks. Lineage-based matching saves permanent keys at the cost of recording continuity before a refactor can be interpreted. The independent same-value selections exercised here work with all three approaches. [RT-24 identity matrix](RT-24-IDENTITY-DECISION-MATRIX.md) · [LL-002](../TODO.md#ll-002--define-operation-stable-id-lifecycle)

## 6. Artifact granularity and trade-offs

| Artifact | Candidate addressable unit | Reason and constraint |
|---|---|---|
| Requirement and contract | One independently reviewed requirement or reusable contract, with local clauses and role labels | Multiple obligations can trace to one contract. Review and version exact clauses when a single requirement is too coarse. |
| Operation and interface | One operation definition with exact interface and contract references | A binding can change providers while the operation stays usable. Named exports and parameters with observable binding rules participate in the interface. |
| Type | One nominal or reusable structural definition | Preserve nominal distinctions required by the semantic profile. Keep local type expressions inline until independent reuse warrants an address. |
| Implementation component | One callable body, with inline expressions and structural call positions. Publish one group for exact recursive components. | A local edit should affect its exact dependents. A body-sized unit keeps expression traversal local. Group edits can widen invalidation. |
| Test specification and verification model | One independently run test/test set or model with explicit assumptions and a shared subject reference | A change to a test definition or model can be tracked separately from a change to the subject. |
| Proof and run evidence | One judgment or run record with exact subject, claim, assumptions, tool and relevant context | Model, proof object, and checker result can each have an address. Evidence freshness follows action inputs. |
| Generated artifacts | Output boundary of a declared build action | Platform or optimizer changes can invalidate this output while preserving a source value. |

A single fully resolved snapshot blob is a viable implementation baseline for a small system. It reduces object bookkeeping and gives a single invalidation boundary. Layered, callable-sized values allow the operation, the binding, and the unrelated body to be reused separately in the experiment. Expression-sized global objects can offer finer reuse when expressions are closed over exact typed inputs. They also require more objects and explicit treatment of local scope and order. Any size or latency advantage needs a representative workload. The experiment compares the selected values that change and makes no storage or performance estimate. [LL-006](../TODO.md#ll-006--decide-artifact-granularity-for-the-initial-spgstore) · [Semantic compilation cache](SEMANTIC-COMPILATION-CACHE.md)

## 7. Results and falsifiers

| ID | Evidence | Result and scope |
|---|---|---|
| SPG-01 | Experimental result | All 32 generated pairs of infix and prefix bodies yielded the same selected snapshot and byte-identical graph export within each pair. Each pair ran on seven integers. Both frontends matched an independent arithmetic and event oracle for all 224 paired observations. |
| SPG-02 | Experimental result | Swapping effectful addition operands kept the return value `5` and reversed the event order. Changing argument order also changed the numeric answer. The typed values differed. Reordering the outer contract set preserved bytes. Reordering or repeating an event inside the only allowed trace changed the contract address. Three isolated injected faults, reversed evaluation, sorted inner traces and deduplicated inner traces, each triggered the predicted assertion failure. |
| SPG-03 | Experimental result | Changing the binding from `primary` to `alternate` changed exactly one of the fixture's 13 selected entries. The operation caller returned `5` before the update and `6` after it, with the same caller hash and trace. The concrete caller kept returning `5`. Editing the primary body changed exactly the binding, the edited body and its exact caller. Changing the provider's contract changed seven selections, including both kinds of caller. |
| SPG-04 | Experimental result | Both recursive group policies matched the parity oracle on `0` through `12`, for 26 observations. Both reported call-budget exhaustion at one call below the needed budget. Removing a back edge changed the two former group members and their exact entry caller. In a separate symmetric fixture, the structural policy shared an address across two selected slots and the keyed policy gave two addresses. |
| SPG-05 | Experimental result | Two copied selections shared one value address. Lineage-only comparison left the split unmatched without a relation, accepted declared split and merge relations, and rejected a stale endpoint state. A replacement with equal contents and a fresh selection gave no continuation. Moving an origin record and attaching reported evidence changed side records while preserving semantic export. |
| SPG-06 | Experimental result | The fixture compiler rejected 16 malformed, ill-typed, or unresolved input cases. The interpreter separately rejected a Boolean argument where `Int` was declared. A stored binding declaration still admitted a witnessed trace outside the provider's declared contract. That observation falsifies treating the declaration as conformance evidence. |
| SPG-07 | Experimental result | Reloading the fixture graph and re-encoding produced the same bytes and the expected dispatch observation. Fresh processes with two hash seeds produced identical dispatch export bytes. |

SPG-01 would fail if either parser changed name, literal, or argument interpretation. SPG-02 supplies counterexamples to canonicalizing ordered collections as sets or evaluating operands in a different order. SPG-03 is a counterexample to execution reuse based only on the caller value. SPG-04 and SPG-05 delimit the difference between value addresses and managed selections. These are high-confidence results for the recorded fixtures. Coverage of a full parser, context, or runtime requires further experiments. [Reproduction corpus](PROTOTYPES/DEPENDENCY-GRAPH-01/tests/test_spg_representation.py)

SPG-02 also compares nested emission with an addition that emits the same two events in the same order. Both return `5` with the same trace at input `4`, while the two bodies retain distinct addresses. This fixture's value equality tests structural identity after lowering. Behavioral equivalence is a separate judgment.

## 8. Reproduction and limits

From `research/PROTOTYPES/DEPENDENCY-GRAPH-01`, run the standard-library-only experiment. The generator exhausts four literal offsets, two arithmetic operations, two branch label assignments, and two call modes. Input order and parameters also vary between the two surfaces. Call budgets in the reported corpus are at most 64. The comparisons ran on CPython 3.12.14, Linux 6.18.57 x86-64.

```sh
python -B -m unittest -v tests.test_spg_representation

spg_out=$(mktemp -d)
for seed in 1 991; do
  PYTHONHASHSEED="$seed" python -B -c 'import sys; from tests.test_spg_representation import dispatch_program, encode; from src.spg_representation import compile_program; sys.stdout.buffer.write(encode(compile_program(dispatch_program())))' > "$spg_out/$seed.json"
done
cmp "$spg_out/1.json" "$spg_out/991.json"
sha256sum "$spg_out/1.json"
```

Expect 11 passing experiment tests and `6e408a37fdffd6399860f25b00fbdf50d3593d5833b15a58231ba4304f2abcbe` for the dispatch export. To reproduce the fault injections, apply each substitution independently to a temporary copy of the prototype and rerun the indicated test on that copy.

| Replace in `src/spg_representation.py` | Substitution | Test that should fail |
|---|---|---|
| `return evaluate(left) + evaluate(right)` | `return evaluate(right) + evaluate(left)` | `test_effect_order_is_observable_even_when_result_and_event_set_match` |
| `sorted(set(traces))` | `sorted({tuple(sorted(trace)) for trace in traces})` | `test_contract_set_canonicalization_keeps_trace_order_and_multiplicity` |
| `sorted(set(traces))` | `sorted({tuple(dict.fromkeys(trace)) for trace in traces})` | `test_contract_set_canonicalization_keeps_trace_order_and_multiplicity` |

The 158-test semantic-index workflow selection plus experiment passed, and the separate RT-04 prototype suite passed all 364 tests. Full Dependency Graph discovery ran 397 tests with one failure and one optional Z3 skip. A clean archive of the baseline ran 386 tests with the same failure and skip. `test_analysis_bound_returns_unknown_not_success` expected `UNKNOWN` and received `NEEDS_REVIEW`. [Semantic-index workflow selection](../.github/workflows/semantic-dependency-index.yml)

Both textual frontends share a type checker, canonicalizer, and evaluator. The independent oracle targets the generated arithmetic and event cases. Foreign functions, nominal and recursive types, mutable aliasing, resource ownership, effect handlers, macros, concurrency, and compiler lowering are beyond that evidence. The call-budget check reports exhaustion without returning a partial event trace. Loaded graph fixtures exercise persistence integrity and replay, while validating arbitrary imported graphs would require a dedicated schema checker. The corpus supplies no independent source-completeness proof, cache benchmark, or merge evaluation.

## 9. Decision boundary and traceability

Advance the layered, callable-sized candidate for another comparison. Use typed, exact references for changes to contracts and pinned calls. For execution-sensitive actions, the SPG-03 witness requires collecting the relevant binding and selected implementation closure alongside the caller value, assumptions, and action context. As scope grows, RT-06 must establish the closure or the action needs a conservative invalidation decision. The selection of an identity policy, hash format, and language profile remains open, and §1.1 stays partially validated. [Plan §1.1](../PLAN.md#11-semantic-program-graph-and-program-representation) · [Semantic dependency index](SEMANTIC-DEPENDENCY-INDEX.md)

| Area | Follow-through from this study |
|---|---|
| RT-03/04 · DEP-005/006 | Check the normalization boundary against owned results, alias roles, checked errors and observable cleanup order. These cases constrain which typed fields must survive lowering. |
| RT-06/11/20 · DEP-009/012/052 · LL-005/008/021/023 | Trace exact and binding-resolved dependencies independently. Measure affected actions and verify effect-sensitive reuse when a callee or a binding changes. |
| RT-05/24 · DEP-087 · LL-001/002/004/006 | Compare the surviving continuity policies, recursive address costs, and source inventory import in the semantic merge research. |
| Candidate specification | This is evidence for future graph representation and identity sections. A transfer into `draft/` requires choosing a semantic profile, validation of the broader boundary, and an explicit project decision. |

[Research dependency map](RESEARCH-DEPENDENCY-MAP.md) · [Open questions](../TODO.md) · [Canonical representation and merge](RT-24-CANONICAL-SEMANTIC-REPRESENTATION-DIFF-AND-MERGE.md)

## Public-interface integration (2026-11-24; proposed)

Add a candidate public-operation view to the typed graph: ExportName/catalog revision -> exact Operation (OpHash) -> public Contract; Implementation -> provided Contract; Binding selects exact Operation and Implementation; evidence relates exact body and both contracts. A public interface group may own member operation references and joint invariants; its identity is not automatically any member OpHash. An implementation may provide several operations, but each conformance judgment is separate. Names, logical continuity, immutable values, and scoped export selections must be separated; external name observability determines hash relevance. Direct concrete calls remain distinct from abstract operation calls. Reject dangling, wrong-kind or conflicting edges and missing observation/profile correspondence; no schema is selected.

Related: [Public interfaces and verified contract refinement](PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md). This is a candidate follow-up; it does not change accepted rules or previously reported evidence.

## RT-36 follow-up: explicit assumptions (proposed)

Keep canonical SPG semantics and exact binding identities separate from PDG and assumption authorization/evidence projections. Research typed premise identity, scope, reverse dependency queries and complete closure without a second semantic authority. See [RT-36 — Formal Verification Assumptions, Trust Boundaries and Conditional Proof Management](RT-36-FORMAL-VERIFICATION-ASSUMPTIONS-AND-TRUST.md). This cross-reference does not change adopted rules or previously reported evidence.
