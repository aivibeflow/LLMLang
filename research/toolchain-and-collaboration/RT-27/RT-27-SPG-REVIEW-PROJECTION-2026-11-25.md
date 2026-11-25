# RT-27 readable SPG review projections and generated metadata

**Date** 2026-11-25 · **Plan** §4.2 · **Issue** [#320](https://github.com/aivibeflow/LLMLang/issues/320)

The fixture generates a readable text view of the typed SPG prototype. It lists selected contracts, operations and implementations. It shows each binding with the provider name and exact implementation hash. A separate review receipt identifies the selected semantic root, projection profile and text digest. A reader reconstructs and validates the exact graph from its Git revision and independently regenerates the view.

| Control | Git and review outcome |
| --- | --- |
| Repack the same graph from four record buckets to two | Six storage paths change. The generated text and its receipt remain byte-identical. |
| Rebind the provider under the same storage profile | The ordinary Git diff shows the binding moving from the primary to the alternate provider with its exact hash. |
| Copy a previous receipt to the later revision | The reader refuses the stale subject and digest. |
| Change the review and recompute an internally matching receipt | Independent rendering from the exact graph detects the different text and refuses the metadata. |

Five Git revisions remain readable in a clean clone with its origin removed. The regenerated text is stable for the same graph and projection profile. Physical layout changes remain visible through ordinary Git paths. Review text is derived from the graph and a candidate's admission still depends on complete semantic validation.

The fixture covers one typed prototype and locally supplied revision pins. Broader semantic diff coverage, human review usability, generated metadata authority, hosting integration and a canonical Git storage format remain open.

Reproduce with CPython 3.12.14 and Git 2.52.0 from the repository root.

```bash
study=research/toolchain-and-collaboration/RT-27/SPG-REVIEW-PROJECTION-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two fresh clones reproduce the projection identities and native Git diff byte for byte.
