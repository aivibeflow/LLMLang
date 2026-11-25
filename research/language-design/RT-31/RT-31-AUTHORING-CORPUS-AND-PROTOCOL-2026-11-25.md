# RT-31 profile-independent authoring corpus and controlled comparison

The verified corpus supplies three two-step tasks with one shared semantic acceptance boundary. The comparison protocol assigns those tasks to four syntax profiles while pinning model, instructions, context, Toolchain and environment. The 96 checked assignments are a study plan. They contain no live model outcomes.

## Corpus and acceptance

The three tasks cover changing a selected provider and adjusting behavior, pinning a provider while changing an argument, and preserving or changing ordered effects while editing a fallback. Each stage has its own expected semantic edit scope and independent value and trace obligations. A correct terminal state cannot compensate for an invalid earlier stage.

The original corpus records 504 observations across four profiles and 24 refused controls. The controls cover missing stages, invalid syntax or admission, wrong value or binding, equal values with a different trace, and edits outside the intended scope. The assignment checker pins the original task file and evidence before scheduling. [Staged authoring corpus](RT-31-STAGED-AUTHORING-CORPUS-2026-11-25.md) · [Frontend and semantic layers](RT-31-SYNTAX-AND-SEMANTIC-LAYER-BOUNDARIES-2026-11-25.md)

## Controlled assignment

| Dimension | Required pin |
| --- | --- |
| Model and provider | Approved endpoint identity, exact model revision, invocation settings, and seed support |
| Task and context | Task revision, original semantic state, allowed context and coverage, instructions and acceptance oracle |
| Syntax factor | Concrete profile and version, syntax examples matched for content, and selected assignment order |
| Toolchain and environment | Exact Toolchain, runtime, parser and verifier versions, provider framing, and permitted tools |
| Attempt budget | First submission and predeclared repair count, with each validation or repair bound to its own attempt |

The design uses four counterbalanced orders. Every profile appears once in each position and each distinct directed adjacent pair occurs once. Crossing three tasks, two synthetic seed labels, four order blocks and four profiles yields 96 distinct assignment IDs. The study checker changes each pinned field independently and confirms it changes the assignment ID.

Before live execution, fill every fixture identity with an approved exact value and freeze the planned analysis and independent oracle. Record unsupported seed behavior, provider drift, ineligible contexts and abandoned attempts. Report first-pass and repaired outcomes separately. The checked plan neither estimates variance for live model outcomes nor establishes a representative research sample. Approved provider access and independent real-task evaluation remain open.

## Reproduce

Use CPython 3.12.14. Python hash seeds 37 and 71 reproduce evidence SHA-256 `5f4bf90e0c6e917bf9ace0575fc96faf8473c32f3ad813ce90a5ad4acd081ff0`. [Assignment evidence](AUTHORING-PROTOCOL-01/evidence.json)

```sh
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python research/language-design/RT-31/AUTHORING-PROTOCOL-01/check.py > /tmp/rt31-authoring-plan.json
```
