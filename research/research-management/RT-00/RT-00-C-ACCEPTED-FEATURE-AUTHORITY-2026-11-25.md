# RT-00 C — Trace accepted feature status to durable decisions

## Question and method

Which features are recorded as accepted, and how far does each supporting decision reach? I reviewed all 143 feature rows and all five decision files under `docs/adr/` and `draft/ARCHITECTURE-DECISIONS.md` at `e2e41096c5eeaba8bd35f7aa94e31eea02a45ca7` on `research/all`. I mapped the status field to the source decision in both directions. Then I read the exact scope, exclusions and status of neighboring ADRs. This checks agreement between the registry and decision authority. The two-row mapping contains the relevant relationships without a diagram. [Feature registry](../../../FEATURE-REGISTRY.md) · [Exact scope ledger](RT-00-C-ACCEPTED-FEATURE-AUTHORITY-2026-11-25.json)

## Findings

| Feature and registry status | Explicit accepted scope | Adjacent questions kept separate |
|---|---|---|
| F-PORT-002, Accepted | Published component versions are immutable. A coherent build checks each caller-to-callee binding under one Toolchain version. | Behavioral contract refinement, cross-version binary/plugin ABI and wire-schema evolution are separately scoped. |
| F-TOOL-003, Accepted (scoped) | JSON is the default representation of SPG objects exchanged with agents through MCP. References between independently addressable objects use SPG IDs. | Toolchain operations and capabilities, repository representation, canonicalization and Content Hash remain separate. ADR-015 still records the proposed semantic development API, and ADR-014 records the proposed Git representation. |

Each accepted registry row refers to one durable accepted source, and each of the two accepted decision sources has a corresponding registry row. Matching only `Accepted` would omit F-TOOL-003. Matching the whole status field allows the qualifier to remain part of the result. In particular, the title of F-TOOL-003 covers a broader adapter capability than the exact accepted format rule. The scoped status and body text retain the governing boundary. [Component decision](../../../draft/ARCHITECTURE-DECISIONS.md) · [ADR-017 object format](../../../docs/adr/017-mcp-agent-object-format.md) · [ADR-015 Toolchain API](../../../docs/adr/015-toolchain-server-semantic-api.md) · [ADR-014 Git representation](../../../docs/adr/014-git-semantic-merge.md)

These dispositions are about architecture authorization. They provide no proof of implementation, interoperability or capability completeness. Research for broader choices can cite each decision's constraint without extending its scope. This audit covers decision authority in the two stated locations and the pinned registry. The full feature compatibility review and independent review remain pending. [Stage 0.2 tracking](https://github.com/aivibeflow/LLMLang/issues/285)

## Reproduction

Git 2.56.1 can enumerate the exact registry and source headers. The accepted rows should be F-TOOL-003 and F-PORT-002. The decision-source comparison requires reading the cited decisions against their rows.

```bash
rev=e2e41096c5eeaba8bd35f7aa94e31eea02a45ca7
git grep -c -E '^\| F-[A-Z]+-[0-9]+ \|' "$rev" -- FEATURE-REGISTRY.md
git grep -n -E '^\| F-[A-Z]+-[0-9]+ \|.*\| Accepted( \(scoped\))? \|' "$rev" -- FEATURE-REGISTRY.md
git grep -n -E '^(\- )?\*\*Status' "$rev" -- docs/adr draft/ARCHITECTURE-DECISIONS.md
```
