# Contributing

## Project language

Write project files in English, including documentation, plans, ADRs, RFCs, code comments, and user-facing strings.

## Keep the RFC in sync with ADRs

When adding an architecture decision record under `draft/adr/`, update the [LLMLang architecture RFC](draft/RFC.md) in the same change. Summarize a new accepted decision in the affected RFC sections and link to its ADR. Record a proposed ADR as open work with its status and a link. Apply the same rule when an ADR changes status, is superseded, or changes in a way that affects the RFC. Cite a same-change ADR by its repository-relative path and check the relevant references and diagrams before submitting the change.

## Install repository Git hooks

Run this once in your checkout to enable the repository's local hooks:

```sh
git config core.hooksPath .githooks
```

The pre-commit hook checks the staged contents of every Markdown file for valid UTF-8 and disallowed control characters. It reports failures and blocks the commit; it does not modify files. CI runs the same checker as a required merge gate.
