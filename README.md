# LLMLang

**LLMLang** is an experimental concept for an AI-native programming language and development environment designed around large language models as primary program authors, with independent machine validation of their output.

> **Core principle:** Don't make the LLM remember the rules. Make the language and its tooling enforce them.

## Concept

LLMLang explores a programming model in which a program is represented as a typed **Semantic Program Graph (SPG)** rather than only as source text or a conventional AST.

The concept is organized around three connected, independently optional layers:

- **Specification Graph** — what the program must do: requirements, contracts, invariants, states, and constraints.
- **Design Graph** — how the program is structured: components, interfaces, dependencies, algorithms, and data structures.
- **Implementation Graph** — how the program is implemented: expressions, instructions, control flow, memory operations, and runtime calls.

Key areas include:

- First-class preconditions, postconditions, invariants, effects, and errors.
- Static strict typing, algebraic data types, refinement types, and typed states.
- Explicit ownership, resource management, concurrency, and capabilities.
- Traceability between requirements, implementation, tests, and proofs.
- Deterministic compiler validation independent of the LLM.
- Interpreter/VM execution during development and a possible native-code backend.

The LLM proposes structured program changes; the compiler and verification tools independently validate them. An LLM response is never treated as proof of correctness.

## Status

This repository contains a **conceptual research document**, not a production-ready language implementation. Syntax, formal semantics, type-system details, verification strategy, and implementation architecture remain subjects for research and prototyping.

## Document

See [LLMLang-CONCEPT.md](LLMLang-CONCEPT.md) for the full concept, architecture, design principles, proposed toolchain, development stages, and open questions.

## Guiding boundary

Formal verification can establish that an implementation satisfies a formal specification under stated assumptions. It cannot, by itself, establish that the specification fully captures the human's actual intent.
