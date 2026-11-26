# Contributing

## Project language

Write project files in English, including documentation, plans, ADRs, RFCs, code comments, and user-facing strings.

## Keep the RFC in sync with ADRs

When adding or changing an architecture decision record under `draft/adr/`, update the [LLMLang architecture RFC](draft/RFC.md) in the same change. Synthesize the current accepted decisions by topic into self-contained architecture text. Merge overlapping decisions into one description of the resulting design and resolve amendments and supersessions before writing. Keep proposed decisions out of the accepted architecture. Where relevant, describe unresolved questions under open work. Keep ADR links exclusively in the RFC's Sources section. Read each affected section as a whole and check that its text, diagrams, and source list agree.

## Install repository Git hooks

Run this once in your checkout to enable the repository's local hooks:

```sh
git config core.hooksPath .githooks
```

The pre-commit hook checks the staged contents of every Markdown file for valid UTF-8 and disallowed control characters. It reports failures and blocks the commit; it does not modify files. CI runs the same checker as a required merge gate.
