# Prototype 29 — Verified SMT Proof Checker Integration

**Status:** Process-runner prototype implemented; actual cvc5/Logos integration not executed.  
**Date:** 2026-11-17  
**Related research:** [RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md](../../RESEARCH-SCENARIO-29-VERIFIED-PROOF-CHECKER-AND-ENCODER-VALIDATION.md)

## Implemented

- \`src/logos_runner.py\` — fail-closed subprocess adapter for pinned cvc5 and Logos executables.
- \`tests/test_logos_runner.py\` — fake-executable tests for the process and verdict boundary.

The adapter:
- checks the SHA-256 of both executables before running them;
- invokes cvc5 with CPC proof output and explicit proof granularity;
- distinguishes SAT, UNSAT, and UNKNOWN solver responses;
- does not invoke Logos for SAT or UNKNOWN;
- preserves the exact CPC proof bytes and their SHA-256;
- maps Logos \`correct\`, \`incorrect\`, and \`incomplete\` to distinct statuses;
- fails closed on missing binaries, hash mismatch, unexpected output, nonzero exit, and timeout.

**Critical limitation:** a Logos \`correct\` response is returned as \`CHECKER_REPORTED_CORRECT_UNBOUND\`. The adapter does not compare the parser's assumption AST to the canonical LLMLang query AST. It cannot issue \`PROVEN_INDEPENDENCE\`.

## Tests

Executed in an isolated local workspace with fake cvc5/Logos executables:

\`\`\`bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
\`\`\`

Result:
- 15 tests passed;
- 0 failures;
- \`compileall\` passed.

These tests validate only process handling, hash pinning, timeout behavior, and fail-closed status mapping. They do **not** validate a real cvc5 binary, a real Logos binary, CPC proof parsing, or mathematical proof soundness.

## Environment limitation

The current environment has none of the required tools installed: cvc5, Z3, Lean, Lake, Logos, Rust, or Cargo. Therefore:
- no real CPC proof was generated;
- no real Logos proof check was run;
- no Logos full proof build was performed;
- no assumption-binding Lean wrapper was compiled;
- no QF_LIA semantic correspondence or LLMLang encoder theorem was proved.

## Next gate

Implement the Lean assumption-binding wrapper, add the QF_LIA validator/encoder and its correctness theorems, install/pin the toolchain, and run a golden proof plus corrupted/mismatched-proof tests. Until then all checker results remain unbound reports, never LLMLang proof statuses.


## Source commit

Process-runner implementation and its 15 tests were committed in `c0037ce42bf9b7965d5b67008e1a7899798ac6b9`. The local files used for the 15-test run have the same Git blob SHA values as the committed source and test files.
