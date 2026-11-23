# RT-00 C — Scenario 102 result-policy current-source reproduction

**Date:** 2026-11-23  
**Baseline:** `fc170126d36e45b1453f4958c47b9f4d92e5e5cf` (`main`)  
**Scope:** clarify the reported seven-versus-eight test count and reproduce the current result-policy test file.

## Reproduction

Ran on CPython 3.12.14:

```sh
python3 -B -m unittest discover \
  -s research/PROTOTYPES/RT-04-01 \
  -p test_rt03_feasibility_outcomes.py -v
```

**Result: 8/8 passed.** Current source SHA-256 values:

- `rt03_feasibility_outcomes.py`: `8a385428324a59fd35c7600c980acfe716d00968c277ddcbe36eea260ed5366b`
- `test_rt03_feasibility_outcomes.py`: `cd0a698be53ad7aa3eecf95411730761d9af226d9448b1b4e23919d3e63307e0`

The eight methods belong to the **result-policy adapter** test file and cover replayed/candidate SAT witnesses, incomplete or stale evidence, timeout/unknown/error outcomes, untrusted UNSAT, and explicitly accepted UNSAT evidence bases. Separately, `test_rt03_sympy_predicate_paths.py` currently has **three** DPLL/SymPy path-analysis methods; it is not the file represented by the eight result-policy fixtures. The fixed-seed 128-formula CI cross-check is also distinct from both method counts.

The current result-policy test file blob is identical to the blob present in Required CI commit `b808c3a8f984bbc5c175ecf45d61e0e8db7a00bb`; this supports applicability of that CI result to these unchanged test sources. The local rerun adds exact current-main interpreter and command evidence.

## Provenance boundary

Scenario 102's report records a historical focused run of seven tests, but the exact revision/source blob for that run was not retained. The current eight-test file and the separate three-test DPLL file do not identify what the older runner discovered. Do not rewrite the historical count or infer its exact source revision from today's file.

This closes the reproducibility question for the current eight-test result-policy file only. The older focused run's exact source/toolchain provenance remains unresolved and is explicitly external to the current repository evidence.
