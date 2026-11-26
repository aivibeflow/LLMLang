# Draft

This directory contains the current candidate specification and its supporting terminology.

- [Agent bootstrap](docs/bootstrap.md) — entry point for working with LLMLang source and packages.
- [Syntax reference](docs/lang.md) — implemented scalar source and structured MCP forms.
- [MCP server guide](docs/server.md) — setup, package authoring, verification, and build scenarios.
- [LLMLang architecture RFC](RFC.md) — integrated description of the accepted architecture and its open boundaries.
- [GLOSSARY.md](GLOSSARY.md) — shared terminology for semantic identities, operations, implementations, and conformance classes.
- [ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md) — accepted project architecture decisions and their boundaries.
- [Architecture decision records (ADRs)](adr/) — numbered records with their individual decision statuses.
  - [ADR-025 — Optional embedded library contracts](adr/025-optional-embedded-library-contract.md) — accepted decision to embed `llmlang_contract` by default with a per-library opt-out.
  - [ADR-031 — LLMLang Server and MCP package authoring for the MVP](adr/031-llmlang-server-mcp-package-authoring.md) — accepted requirements for the package authoring workflow.

Research proposals and alternative designs belong in [`research/`](../research/) and do not become normative merely by being referenced here.

Related non-normative research: [Public interfaces and contract refinement](../research/semantic-representation/RT-05/PUBLIC-INTERFACES-AND-CONTRACT-REFINEMENT.md) extends operation/implementation terminology; no accepted draft semantics are changed.
