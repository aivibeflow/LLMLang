# Contributing

## Project language

Write project files in English, including documentation, plans, ADRs, RFCs, code comments, and user-facing strings.

## Keep the RFC in sync with ADRs

When adding or changing an architecture decision record under `draft/adr/`, update the [LLMLang architecture RFC](draft/RFC.md) in the same change. Synthesize the current accepted decisions by topic into self-contained architecture text. Merge overlapping decisions into one description of the resulting design and resolve amendments and supersessions before writing. Keep proposed decisions out of the accepted architecture. Where relevant, describe unresolved questions under open work. Keep ADR links exclusively in the RFC's Sources section. Read each affected section as a whole and check that its text, diagrams, and source list agree.

Every ADR and the RFC must be self-contained within its stated scope. Include the full decision, applicable data definitions, constraints, and behavior directly in the document. When a decision defines a schema, include its complete affected schema with columns, logical or physical types as applicable, required and optional fields, keys, and relationships. Include diagrams and examples where they are needed to interpret the design. External references may support provenance or provide additional evidence. A reader must be able to understand and apply the decision from the document itself. Keep shared schema definitions and diagrams synchronized whenever the design changes.

## Install repository Git hooks

Run this once in your checkout to enable the repository's local hooks:

```sh
git config core.hooksPath .githooks
```

The pre-commit hook checks the staged contents of every Markdown file for valid UTF-8 and disallowed control characters. It reports failures and blocks the commit; it does not modify files. CI runs the same checker as a required merge gate.
