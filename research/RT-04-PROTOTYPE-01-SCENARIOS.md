# RT-04 Prototype 01 — Executable Scenario Set

Implemented by PROTOTYPES/RT-04-01/test_rt04_model.py. Scope is declaration-level checker behavior.

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
| RT4-P07 | Same resource consumed twice | No static affine rejection | Reject use-after-move |
| RT4-P08 | Unknown resource consumed | No static affine rejection | Reject |
| RT4-P09 | Unknown callee | Reject | Reject |
| RT4-P10 | Unknown effect label | Reject outside closed vocabulary | Currently accepted as effect-row label |
| RT4-P11 | Malformed envelope | Reject | Reject |

These are not whole-program semantics. RT4-P04 assumes the supplied call graph is complete; RT4-P05/P06 do not exercise runtime authorization; RT4-P07 does not test branch-sensitive control flow.
