# Loaded provider identity and foreign-thread callback teardown

[GitHub #329](https://github.com/aivibeflow/LLMLang/issues/329) · 2026-11-25

Two byte-identical native provider libraries are loaded from separate files in one process. Each holds its own session generation, worker, callback and completion count. A caller lends a callback and its context until the provider's join returns. The provider calls it on a POSIX worker thread outside the session mutex. The callback can reenter the provider and check the exact generation and worker identity.

The worker starts parked. The host selects cancellation or delivery before releasing it. Canceling prevents callback invocation and preserves the caller's result variable. Both paths join the worker before clearing borrowed addresses. A registration or close request while the callback is pending returns busy. Duplicate finish and stale session use are refused. The test also attempts old tokens after opening successor sessions.

C++ catches a thrown exception inside its C-compatible callback. Rust catches an unwinding panic inside its C-compatible callback and installs a quiet fixture-local panic handler. The CPython callback catches its own exception before returning through the C callback adapter. Each maps the injected failure to the same explicit status. The wrong-provider control uses a live library instance with an equal raw token. The worker check rejects its reentry in all three languages.

## Observations

The runner checks 96 scheduled scenarios across three bridges, two providers, four dispositions and four payloads. It observes 72 callback completions and 24 cancellations before invocation. Both independent instances complete exactly 36 callbacks. In 94 attempts, an old session token is refused while the new one is open. All result values and invocation deltas match the independent assertions. Two fresh temporary roots reproduce the four ELF digests and the full trace ledger.

The experiment uses a single active worker per provider and cancellation before delivery. Calling conventions, runtime initiation, callback lifetime, join and containment are demonstrated in the tested configuration. Callback cancellation after entry, concurrent foreign callers, cross-platform threading, dynamic unload while a callback is live, additional runtime implementations and a production allocation-failure path remain open.

## Replay

Use CPython 3.12.14, GCC/G++ 14.2.0, Rust 1.85.1 and Linux x86-64 with glibc 2.41.

```sh
fixture=research/compiler-and-translation/RT-13/FFI-LOADED-CALLBACK-01
python "$fixture/run.py" --output /tmp/rt13-ffi-callback.json
cmp "$fixture/evidence.json" /tmp/rt13-ffi-callback.json
```

The [evidence ledger](FFI-LOADED-CALLBACK-01/evidence.json) includes the exact native trace, source and ELF identities.
