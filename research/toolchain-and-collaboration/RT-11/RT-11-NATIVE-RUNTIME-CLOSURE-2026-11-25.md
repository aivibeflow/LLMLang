# RT-11 native runtime closure and incomplete cache inputs

**Date** 2026-11-25 · **Plan** §3.3 · **Issue** [#300](https://github.com/aivibeflow/LLMLang/issues/300)

One x86-64 Linux ELF executable calls a shared object that calls a second shared object. GCC builds two versions of that transitive leaf with the same SONAME. Their only behavior in the fixture is to return 17 or 29. `readelf` confirms that the driver does not directly request the leaf and that neither the driver nor its intermediate provider embeds a search path. The glibc loader lists selected files independently of running the executable. The runner hashes the selected files and forces every execution in a fresh temporary fixture to serve as an oracle for lookup decisions.

| Control | Checked result |
| --- | --- |
| Reverse two directories with all files unchanged | The same executable changes from 17 to 29. Sorting the search configuration would lose that distinction. |
| Place the second provider in a previously empty earlier directory | The search configuration and executable bytes stay equal, but the result changes from 17 to 29. The recorded prefix includes absent candidates before the selected leaf. |
| Shadow with byte-identical provider or restore original ordering/state | The byte-identical shadow returns 17 with a new exact key for the changed selected path and prefix. Restoration yields an exact hit. |
| Withhold the loader closure from the cache coordinator | Both requests skip lookup and publication. The independent run can still produce 29, which is diagnostic only until the runtime identity and policy are verified. |
| Remove every candidate | Two forced runs report a missing shared object and create no entries in this fixture. |
| Narrow the allowlist with the same successful native load | The request is refused on both attempts despite a previous receipt for those exact runtime bytes under the broader policy. |

The 14 requests produce four publications, four hits, two unknown-closure skips, two policy refusals and two loader failures. The test action's output includes its observation, so a repeatable observation that fails the test predicate can be retained when the exact action is eligible. All cached observations equal their independent native outputs.

Bind each action to its exact subject, runner identity and version, configuration, target, relevant environment, resolution context, dependency closure and policy. For this action the closure includes the loader and every listed file mapping, with an ordered leaf search prefix recording the absent paths. A required input with unknown identity makes the cache request ineligible for both lookup and publication. Update invalidation or rerun in the same declared context if execution policy permits, and derive a cache receipt only after establishing closure. Cache disposition confers no execution authorization.

`--list` is scoped to startup file mappings. Dynamic loads after startup, kernel-provided virtual mappings, broader environment effects, immutability between resolution and execution, generic loader discovery and other toolchains remain open. The diagnostic run uses controlled fixture inputs, including when modeling denied publication. The cache coordinator is in memory.

Reproduce from the repository root with GCC, GNU readelf, glibc and Python on x86-64 Linux.

```bash
study=research/toolchain-and-collaboration/RT-11/NATIVE-RUNTIME-CLOSURE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent fixture builds reproduced the archived output byte for byte. Exact tool and runtime digests are specific to the recorded environment. The replay also asserts every expected decision and observation before emitting the archive.
