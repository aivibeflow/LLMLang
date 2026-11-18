# RT-04 Prototype 01 — Executable Scenario Set

Implemented by PROTOTYPES/RT-04-01/test_rt04_model.py. Scope is declaration-level checker behavior, supplied finite resource-control-flow graphs, and explicitly asserted call-graph completeness metadata.

| ID | Fixture | Profile A | Profile B |
|---|---|---|---|
| RT4-P01 | Primitive signature with fs.read | Accept | Accept |
| RT4-P02 | Open effect row | Reject unsupported | Accept annotation |
| RT4-P03a | Positive refinement value | Unsupported | Accept |
| RT4-P03b | Negative refinement value | Unsupported | Reject |
| RT4-P03c | Missing refinement evidence | Unsupported | UNKNOWN |
| RT4-P04 | entry → load → read; leaf has fs.read | Summary includes effect | Summary includes effect |
| RT4-P05 | Callee requires network.send; caller omits it | Requires ambient context | Reject undeclared caller capability |
| RT4-P06 | Ambient capability in A / explicit caller requirement in B | Accept | Accept |
| RT4-P07 | Same resource consumed twice in a linear sequence | No static affine rejection | Reject use-after-move |
| RT4-P08 | Unknown resource consumed | No static affine rejection | Reject |
| RT4-P09 | Unknown callee | Reject | Reject |
| RT4-P10 | Unknown effect label | Reject outside closed vocabulary | Reject without an open row; accept with an explicit row variable |
| RT4-P11 | Malformed declaration envelope | Reject | Reject |
| RT4-P12 | Two exclusive branches both consume the same resource before join | No static affine check | Accept; incoming states agree |
| RT4-P13 | One branch consumes and the other preserves a resource before join | No static affine check | Reject inconsistent join state |
| RT4-P14 | One reachable branch consumes the same resource twice | No static affine check | Reject use-after-move |
| RT4-P15 | A loop consumes the same resource on successive iterations | No static affine check | Reject use-after-move |
| RT4-P16 | CFG edge points to an undeclared block | No CFG validation | Reject malformed CFG |
| RT4-P17 | Linear consumes and CFG resource_flow both declared | No affine check | Reject ambiguous resource-flow input |

| RT4-P18 | Transitive effects fit a declared effect bound and every reachable function is marked complete | Not yet compared | Accept |
| RT4-P19 | A transitive callee introduces an effect outside the caller's bound | Not yet compared | Reject |
| RT4-P20 | A reachable function lacks call-graph completeness evidence | Not yet compared | UNKNOWN |
| RT4-P21 | No outgoing call edge is listed but the function is not certified complete | Not yet compared | UNKNOWN, not an empty effect summary |
| RT4-P22 | A callee target is unresolved while checking a bound | Not yet compared | UNKNOWN |
| RT4-P23 | A known direct effect violates the bound while another call edge is unresolved | Not yet compared | Reject the known violation and report incomplete summary |
| RT4-P24 | Completeness evidence names an undeclared function | Not yet compared | Reject malformed evidence |
| RT4-P25 | Multiple direct effects are all within the declared bound | Not yet compared | Accept |
| RT4-P26 | Typed call has matching argument and result types | Not yet compared | Accept |
| RT4-P27 | Typed call has wrong argument count | Not yet compared | Reject |
| RT4-P28 | Typed call has an argument type mismatch | Not yet compared | Reject |
| RT4-P29 | Caller expects a result type different from the callee result | Not yet compared | Reject |
| RT4-P30 | Typed call targets a function without an explicit complete signature | Not yet compared | UNKNOWN |
| RT4-P31 | Typed call-site target is absent from caller call-graph edges | Not yet compared | Reject malformed model input |
| RT4-P32 | Result<Ok, Err> descriptors match structurally | Not yet compared | Accept |
| RT4-P33 | Nested Result error component differs | Not yet compared | Reject |
| RT4-P34 | Profile A receives a Profile B Result descriptor | Reject unsupported type | Not yet compared |
| RT4-P35 | Result<Ok, Err> is used as a callee parameter type and matches at the call site | Not yet compared | Accept |
| RT4-P36 | Scoped grant covers a narrower required path | Not yet compared | Accept |
| RT4-P37 | Required path is outside the grant scope | Not yet compared | Reject |
| RT4-P38 | Child grant narrows its parent scope without changing capability | Not yet compared | Accept |
| RT4-P39 | Child grant broadens its parent scope | Not yet compared | Reject malformed grant graph |
| RT4-P40 | Child grant changes its parent's capability | Not yet compared | Reject malformed grant graph |
| RT4-P41 | Revoking a parent grant revokes descendant grants | Not yet compared | Reject use of descendant |
| RT4-P42 | A directly revoked grant is used to satisfy a requirement | Not yet compared | Reject |
| RT4-P43 | Caller explicitly delegates a sufficient grant to a callee that accepts it | Not yet compared | Accept |
| RT4-P44 | Scoped callee requirement has no explicit call-site delegation | Not yet compared | UNKNOWN |
| RT4-P45 | Caller attempts to pass a grant it does not hold | Not yet compared | Reject malformed model input |
| RT4-P46 | Grant scope contains parent traversal | Not yet compared | Reject malformed grant |
| RT4-P47 | Profile A receives scoped grant declarations | Reject unsupported | Not yet compared |
| RT4-P48 | Callee has not declared a passed grant as accepted | Not yet compared | Reject |
| RT4-P49 | Grant parent graph contains a cycle | Not yet compared | Reject malformed grant graph |
| RT4-P50 | Scope prefix matches only on a path-segment boundary | Not yet compared | Reject out-of-scope requirement |

The CFG tests assume the supplied blocks and edges are complete and correctly represent source control flow. They do not model symbolic branch conditions, borrow lifetimes, resource return/drop, terminal-path cleanup, or prove that the CFG extractor is sound. Effect-bound tests likewise trust fixture-level completeness assertions; they do not prove source call-graph completeness or discover dynamic, generated, FFI, handler, or reflective calls. These are not whole-program semantics.
