# Research Scenario 80 — Comments, Documentation, and Lexical Trivia

**Status:** Evidence-linked prior-art comparison; no LLMLang comment or documentation model selected
**Research area:** RT-03 lexical semantics, RT-09 tooling/source mapping, RT-17 API documentation and provenance
**Updated:** 2026-11-19

## 1. Question and boundary

Which comment forms are lexical whitespace, which can affect tokenization, which attach structured documentation to declarations, and which are consumed as tool directives? How should parsers, formatters, source maps, documentation generators, and semantic hashes treat each category?

Scenario 53 already compares statement terminators/newlines and includes a small comment-insertion fixture. This study narrows the focus to comment nesting, comment/newline token behavior, doc-comment association and placement, directive recognition, and retaining trivia for source-preserving tools. It does not select a full doc markup language or repeat the general semicolon-insertion comparison.

## 2. Prior-art comparison

### Rust: nested comments; doc comments desugar to attributes

Rust supports line comments and recursively nested block comments. Ordinary comments act as whitespace. Doc forms are distinct lexical tokens: outer `///` and `/** ... */` comments desugar to `#[doc = ...]` attributes on the following item; inner `//!` and `/*! ... */` forms document the enclosing module/crate. This reuses the attribute placement rules and preserves association explicitly in the syntax model. Doc comments conventionally contain Markdown, but comment termination remains lexical: a `*/` sequence ends a block even inside apparent Markdown or code.

Rust compiler metadata such as `#[cfg]` is an attribute, not a specially interpreted ordinary comment. This separates language/compiler metadata from prose documentation.

Sources: [Rust Reference — Comments](https://doc.rust-lang.org/reference/comments.html), [Rust Reference — Attributes](https://doc.rust-lang.org/reference/attributes.html).

### Go: block comments can be newline tokens; docs are adjacent declaration prose

Go has line comments and non-nesting block comments, which cannot begin inside a string, rune literal, or another comment. A block comment without a newline acts like a space; one containing a newline acts like a newline and can therefore trigger semicolon insertion. This is a distinctive lexical effect: moving a newline into a block comment can alter parsing.

Go doc comments are comments immediately preceding a top-level package/const/func/type/var declaration without intervening newlines. `go/doc` and associated tools parse/reformat this prose; directives such as `//go:build` or `//go:generate` use comment syntax but are consumed by tools and are excluded from rendered documentation. The exact directive grammar and placement therefore matter to build selection and generated artifacts.

Sources: [Go specification — Comments and semicolons](https://go.dev/ref/spec#Comments), [Go Doc Comments](https://go.dev/doc/comment), [Go comments and directives](https://go.dev/wiki/Comments).

### Swift: nested multiline comments; documentation markup is attached to declarations

Swift supports line and nested multiline comments; nested markers must balance. Documentation comments conventionally use `///` and `/** ... */`, and DocC interprets Markdown-like content and documentation directives for symbol documentation. The lexical rules, declaration association, and DocC rendering are related but distinct layers: a comment can be valid trivia without being attached/rendered as API docs.

Source: [Swift Language Reference — Lexical Structure](https://docs.swift.org/latest/documentation/the-swift-programming-language/lexicalstructure/), [Swift Language Guide — The Basics](https://docs.swift.org/latest/documentation/the-swift-programming-language/thebasics/), [Swift DocC](https://www.swift.org/documentation/docc/).

### Zig: line comments only; doc comments are placement-checked syntax

Zig has only `//` line comments—there are no block comments. This lets each source line be tokenized independently. A doc comment starts with exactly `///`; a run of them documents the immediately following declaration/member. `////` is an ordinary comment. `//!` is a top-level doc comment for the containing namespace and must occur before namespace expressions. Doc comments in invalid positions or left unattached are compile errors; ordinary comments may appear between doc-comment lines and are ignored.

This removes nesting and multiline termination ambiguity, and produces strong attachment diagnostics. It means large commented-out blocks need line prefixes and comments cannot shield arbitrary text containing code tokens.

Source: [Zig language reference — Comments, Doc Comments, and Top-Level Doc Comments](https://ziglang.org/documentation/master/#Comments).

## 3. Comparison matrix

| Dimension | Rust | Go | Swift | Zig |
|---|---|---|---|---|
| Ordinary line comments | `//` | `//` | `//` | `//` only |
| Block comments | Nested `/* */` | `/* */`, not nested | Nested `/* */` | None |
| Comment token effect | Whitespace | No-newline block = space; any other comment = newline | Generally trivia; line-sensitive syntax still applies | Line comment ends at LF |
| Doc attachment | Desugared outer/inner attributes | Adjacent top-level declaration prose; package docs | DocC comments attached/rendered by tooling | `///` following declaration; `//!` namespace |
| Invalid/unattached docs | Attribute placement rules apply | Association convention/tool extraction | Compiler/doc tooling behavior is separate from lexical validity | Compile error for invalid/unattached docs |
| Tool/build directives in comments | Prefer explicit attributes for compiler metadata (`cfg`) | `//go:` directive conventions consumed by go/compiler/tools | DocC directives in docs; build/compiler controls use separate constructs | No general comment-directive mechanism in cited model |
| Main trade-off | Rich nested comments and explicit metadata/document association | Familiar forms but comment newlines affect tokens and directives share comment channel | Familiar nested comments with separate DocC layer | Simple lexer and strict docs, but no block comments |

## 4. Discriminating lexer, parser, and tooling fixtures

1. Nest block comments to several depths; include strings resembling comment delimiters inside them and comment delimiters inside strings.
2. Place a newline-free and newline-containing block comment between tokens around statement boundaries, operators, braces, and postfix syntax.
3. Test EOF termination, CRLF, bare CR, Unicode line separators, and comment delimiters split across source encodings/bytes.
4. Attach outer/inner doc comments to package/module, public/private declarations, grouped declarations, fields, generic parameters, expressions, and end-of-file; verify diagnostics and generated API association.
5. Insert ordinary comments between doc comment runs and between a doc comment and its declaration; verify whether association persists or fails.
6. Include Markdown/code examples containing literal `*/`, backticks, raw string terminators, and directive-looking text; verify escaping and rendering.
7. Test build/tool directives in leading, trailing, block, nested, malformed, and ordinary prose positions; compare compiler, formatter, docs, and source-generator treatment.
8. Round-trip a source file through formatter and IDE edits. Preserve or intentionally normalize comment placement, blank lines, source spans, doc attachment, and directive order.
9. Make comment-only edits and measure parse-tree identity, semantic hashes, documentation artifact identity, build selection, and cache invalidation separately.

## 5. Design axes and downstream consequences

- **C-A Comments are whitespace except newline effects:** simple mental model, but block-comment newlines must be specified consistently with statement insertion (Scenario 53).
- **C-B Comments are always trivia and never affect token boundaries:** maximally stable source refactoring; may require explicit terminators/continuation rules.
- **C-C Nested versus non-nested block comments:** nesting simplifies temporary code suppression but requires depth-aware scanning; line-only comments simplify incremental lexing and avoid unclosed-block swallowing.
- **C-D Doc comments as attributes/nodes versus adjacency conventions:** explicit attachment improves semantic tooling and diagnostics; proximity conventions are concise but can be fragile under automated edits.
- **C-E Tool directives in comments versus structured attributes/configuration:** comment directives can bootstrap tooling without new syntax, but make comment-only edits behavior-changing and introduce parser/formatter/tool agreement requirements.
- **C-F Preserve trivia as first-class source-map data versus discard after parsing:** retaining trivia supports format-preserving edits, docs and diagnostics; trivia should remain distinct from executable semantics and may need a separate source/artifact hash.

These vectors can combine and are not recommendations. A compiler must distinguish ordinary prose from build directives before deciding which comments are semantically inert. Documentation extraction should be deterministic and versioned, but generated documentation need not share identity with executable semantics. Source maps should track original comment and newline spans even if comments are omitted from a normalized semantic graph.

## 6. Open questions and falsifiers

- Should a block comment containing a newline affect statement separation? Scenario 53's newline policy must answer this jointly.
- Should nested block comments be accepted, or should the language use line comments only?
- Are doc comments syntax-level attributes, adjacent prose conventions, or structured declaration fields?
- Do unattached/duplicate doc comments produce errors, warnings, or independent module/package documentation?
- Can build directives appear in comments? If so, which exact forms/locations and which tool versions interpret them?
- How are documentation comments parsed, normalized, versioned, rendered, and exposed to IDE/LLM tooling?
- Which file changes invalidate executable semantics, API documentation, build selection, and provenance outputs?

The line-comment-only vector is weakened if generated patches and users find large block edits burdensome. Nested block comments are weakened if they complicate incremental lexing/error recovery in realistic files. Proximity-based doc attachment is weakened if common formatters or refactorings detach docs. Comment directives are weakened if independent tools disagree about their meaning. No LLMLang comment syntax, doc model, or directive channel is selected.

## 7. Evidence quality and temporal limits

Official language references and tool documentation were consulted 2026-11-19. Rust/Swift references are rolling; Zig master is highly version-sensitive. Go's lexical comment rule is in the language specification, while its doc formatting/directive details are tool contracts. No lexer, formatter, doc generator, or semantic hashing prototype was run.
