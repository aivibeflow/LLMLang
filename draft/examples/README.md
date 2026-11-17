# Candidate Example Implementations

This directory contains candidate LLMLang implementations corresponding to task statements in `/examples/`.

**Important status:** LLMLang's concrete syntax and executable toolchain are not yet established sufficiently to claim these files compile. The `.llmlang` files are deliberately written as readable semantic/DSL sketches using concepts from the current research. They are implementation candidates, not validated executable programs.

## Rules

- Each solution directory has the same task ID and slug as its task statement.
- The task statement in `/examples/` is authoritative. Implementations must not weaken or redefine its requirements.
- Keep implementation-specific decisions here; promote any externally observable behavior change to the task statement first.
- Include a requirement-to-code mapping and test status.
- Do not label a solution compiled, tested, or verified unless the corresponding tool actually ran and produced evidence.
