# Agent instructions

These repository-wide instructions apply to agents creating, revising, reviewing, or publishing LLMLang research materials. Follow existing repository contribution requirements and applicable scoped instructions. The rules below govern documentation and evidence presentation; they do not adopt any candidate language semantics or research conclusion.

## ADR and RFC maintenance

When adding or changing an ADR under `draft/adr/`, follow the [contribution rule for updating the RFC in the same change](CONTRIBUTING.md#keep-the-rfc-in-sync-with-adrs).

## Research deliverables: explanations and visual evidence

Research deliverables MUST be self-contained in the repository. Do not leave material explanations, diagrams, comparisons, or experimental charts exclusively in a chat response, PR description, or issue comment.

For every new or materially revised research document:

1. Explain the problem, objective, assumptions, scope, proposed mechanism, alternatives and trade-offs, findings, limitations, and unresolved questions, as applicable. Explain why the result matters to LLMLang. Define non-obvious terminology and notation.
2. Include diagrams wherever they materially clarify architecture, dependencies, data/control flow, algorithms, state transitions, interactions, semantics, or proof structure. Diagrams are part of the research deliverable, not optional chat decoration. If a document is genuinely text-only or a diagram would add no information, briefly explain that choice.
3. Prefer GitHub-renderable Mermaid diagrams embedded in Markdown. Use:
   - Mermaid flowcharts for architecture, pipelines, dependency graphs, algorithms, verification workflows and decision paths.
   - Mermaid state diagrams for state machines and lifecycle transitions.
   - Mermaid sequence diagrams for component interactions, message exchanges, concurrency and protocols.
   - Mermaid class or entity-relationship diagrams where useful for structural models.
   - SVG for mathematical, semantic or other complex illustrations that Mermaid cannot represent clearly. Keep editable source or a reproducible generation script in the repository.
   - Markdown text, tables and LaTeX-compatible mathematics for precise explanations, formulas, comparisons and definitions.
4. For measured experimental results, preserve the underlying machine-readable data (prefer JSON or CSV) and a reproducible chart-generation script (prefer Python), with exact source revisions, tool versions, commands, parameters/seeds and output paths. Include or link the resulting chart when it improves interpretation. Show units, denominators, sample sizes, bounds and uncertainty when applicable. Distinguish measured results from illustrative or proposed values. Never fabricate measurements or present an illustrative diagram as empirical evidence.
5. Place each diagram near the relevant explanation. Provide a caption or surrounding prose explaining its purpose, labels, assumptions and key takeaway. Ensure the substantive meaning remains understandable without rendering the diagram. Use consistent terminology, stable identifiers, readable labels and accessible distinctions that do not depend on color alone.
6. Keep diagrams and explanations synchronized with code, schemas, contracts, proof obligations, experiment configuration and reported results. Link source artifacts and reproducible evidence using stable relative paths or pinned revisions where appropriate. Verify paths, syntax, rendering where feasible, and agreement with the implemented or proposed behavior before submitting a PR. Record any validation not performed.
7. Distinguish candidate architecture, hypothesis, bounded experimental observation, checked proof, independent review and accepted decision. Label illustrative diagrams and proposed models accordingly. Successful tests or attractive visualizations do not establish universal correctness, semantic completeness, or normative status.
8. When revisiting earlier research, backfill missing material explanations and diagrams relevant to the revision. Preserve historical evidence and its provenance; do not silently rewrite prior results. Do not make unrelated bulk changes solely to satisfy presentation requirements.

If an agent presents a substantive research diagram or explanation in a chat or PR summary, it MUST ensure that the corresponding durable research material includes an equivalent representation or a link to it. A summary may be shorter than the repository version. Do not claim that a visualization is committed when it exists only in a conversation.

See [research index](research/README.md), [research quality review protocol](research/research-management/QUALITY-REVIEW-PROTOCOL.md), [research report template](research/templates/REPORT-TEMPLATE.md), and [contributing guide](CONTRIBUTING.md) for existing context. These documentation instructions do not themselves adopt any separate proposed quality protocol or change a research decision's status.

## Research directory organization

Organize research by broad subject direction under `research/<direction>/`. Keep RT identifiers and study names as subdirectories or filenames, not top-level research directions. Place dedicated reports, corpora, prototypes, benchmarks and reproducible evidence in their primary thematic directory; use cross-links for multi-direction work, preserve shared infrastructure and historical pinned paths, and update live links and CI paths after moves. See the [research index](research/README.md) for the direction map.
