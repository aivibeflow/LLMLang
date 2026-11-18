# RT-04 Prototype 01 — Executable Scenario Set

Implemented by PROTOTYPES/RT-04-01/test_rt04_model.py. Scope is declaration-level checker behavior and a supplied finite resource-control-flow graph.

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

The CFG tests assume the supplied blocks and edges are complete and correctly represent source control flow. They do not model symbolic branch conditions, borrow lifetimes, resource return/drop, terminal-path cleanup, or prove that the CFG extractor is sound. These are not whole-program semantics.
