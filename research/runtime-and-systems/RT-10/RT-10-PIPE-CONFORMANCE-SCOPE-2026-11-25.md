# POSIX pipe observations and Linux capacity extensions

[GitHub #326](https://github.com/aivibeflow/LLMLang/issues/326) · 2026-11-25

The candidate evidence scope names the operation, feature, observation view, profile, evidence kind, and schema. The pipe fixture exercises this rule with Linux capacity controls, portable nonblocking write expectations, and a theorem about resuming an exact written prefix. These claims have distinct admission conditions.

## Native and header observations

The runner builds the same C source with GCC 14.2 at `-O0` and `-O2`, statically linked to glibc 2.41 and musl 1.2.5. It checks the linker-selected archive and records its SHA-256. The host was x86-64 Linux 6.18.57.

| Scenario | Outcome in each of four builds |
| --- | --- |
| Request a one-page capacity while two pages are queued | Linux `F_SETPIPE_SZ` returns `EBUSY`. After draining the pipe, the shrink succeeds and `_PC_PIPE_BUF` remains 4,096 bytes. |
| Request 4,096 bytes with half a page occupied | The nonblocking write returns `EAGAIN`. Reading the pipe confirms only the previously queued bytes are present. |
| Request 8,192 bytes with a one-page empty pipe | The write reports 4,096 bytes and reading confirms the exact submitted prefix. |
| Request 4,096 bytes with a one-page empty pipe | The write reports 4,096 bytes and the reader receives the exact payload. |

The 16 native observations agree across both libc profiles and optimization levels. The fixture checks one writer, one kernel and these request sizes. Cross-writer atomicity, other capacities and other operating systems require separate observations.

The four header probes check both libc profiles under `_POSIX_C_SOURCE=200809L` and `_GNU_SOURCE`. Both modes expose `_PC_PIPE_BUF`. The GNU mode also exposes `F_GETPIPE_SZ` and `F_SETPIPE_SZ` on each profile. The declaration probes establish header availability.

## Claim admission

Fifteen admission controls use matching or deliberately changed scopes. Exact records admit separate glibc and musl write observations, the Linux capacity observation, GNU-mode header availability and one formal-model claim. An absent record yields unknown coverage. Changing the evidence digest yields unverified evidence. Changes to the libc, schema, operation, request class, feature or evidence view yield a scope mismatch. Generic POSIX claims from only these host records also fail admission.

The Lean audit checks `exact_prefix_resume` in the existing vector-progress model and reports no axioms for that theorem. Its proof applies to lists split at an admissible prefix length. The fixture binds the proof source and audit transcript and rejects an attempted claim about Linux kernel correctness. The verified-record set is local to the runner. Independent provenance, a selected edition and a complete conformance inventory remain separate work.

## Replay

With Python 3.12, Lean 4.36.0, GCC and a musl development sysroot available, run from the repository root.

```sh
fixture=research/runtime-and-systems/RT-10/PIPE-CONFORMANCE-SCOPE-01
python "$fixture/run.py" --musl-root /path/to/musl --output /tmp/pipe-conformance.json
cmp "$fixture/evidence.json" /tmp/pipe-conformance.json
```

The two runs produced identical [evidence ledgers](PIPE-CONFORMANCE-SCOPE-01/evidence.json) on the pinned host.
