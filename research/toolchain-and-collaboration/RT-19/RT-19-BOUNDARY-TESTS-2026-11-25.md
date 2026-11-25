# RT-19 comparative source editing and failure controls

Four tests exercise the public Toolchain prototype with an independently serialized source input, explicit policy check, and targeted export failure. The fixture composes the existing Toolchain and authorization models without changing either API.

| Test | Verified outcome |
| --- | --- |
| Source editing and typed mutation | Independently serialize equivalent changed declarations in a separate source file. Three edited values produce the same exact snapshot as the typed Change Set. |
| Scoped acceptance | Missing approval, proposal-author self-approval and approval for a different candidate leave the workspace unaccepted. The fixture's exact approved candidate reaches acceptance. |
| Export boundary failure | Inject an error at destination replacement. The existing visible file remains byte-identical, the temporary file is removed, and a retry with the original exact witness publishes the expected bytes. |
| Stale validation | Change the workspace after validating. Acceptance presented with the old result refuses and leaves the newer workspace unaccepted. |

The approval test uses synthetic principal records and calls the existing policy model before the acceptance adapter. The raw prototype lifecycle API does not itself enforce that policy. The failure is injected at a named filesystem API call. System crash, disk durability, general source editing and real authority integration remain separate. All nine existing Toolchain tests and 24 authorization tests also passed. [Independent Toolchain round trip](RT-19-TOOLCHAIN-ROUNDTRIP-2026-11-25.md) · [RT-16 authorization model](../../security/RT-16/RT-16-THREAT-MODEL-01.md)

## Reproduce

Use CPython 3.12.14. Both hash seeds 37 and 71 produce evidence SHA-256 `bcdd7ba857fc9d39dd2025fc37d4594782fa5abc1315310177fe4462d29cc745`. [Evidence ledger](BOUNDARY-TESTS-01/evidence.json)

```sh
LC_ALL=C PYTHONHASHSEED=37 PYTHONDONTWRITEBYTECODE=1 \
  python research/toolchain-and-collaboration/RT-19/BOUNDARY-TESTS-01/test_boundaries.py > /tmp/rt19-boundaries.json
python -B -m unittest discover -s research/toolchain-and-collaboration/PROTOTYPES/TOOLCHAIN-SERVER-01
python -B -m unittest discover -s research/security/PROTOTYPES/RT-16-AUTHORIZATION-01
```
