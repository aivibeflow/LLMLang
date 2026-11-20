"""Execute the resource call workload against SQLite's in-memory C API."""

from typing import get_args

from rt04_close_call_boundary import CallBoundary, ClosePolicy, Fixture, compare, fixtures
from rt04_sqlite_recovery import ERROR, OK, CleanupCall, CleanupResult
from sqlite_cleanup_probe import SQLiteProbe, require


def execute_native(sqlite: SQLiteProbe, policy: ClosePolicy, fixture: Fixture) -> CallBoundary:
    """Run the wrapper's operations without taking a call sequence from the model."""
    flags = dict(fixture.proof.inputs)
    connection = sqlite.connect()
    destructions, _marker, _destructor = sqlite.watch_destruction(connection)
    live = {}
    calls = []
    try:
        observed = sqlite.prepared_statements(connection)
        for statement in fixture.statements:
            sql = b"SELECT abs(-9223372036854775808)" if statement.failed_step else b"SELECT 1"
            handle = sqlite.prepare(connection, sql)
            live[statement.name] = handle
            if statement.failed_step:
                require("local step error", sqlite.step(handle), ERROR)
            if statement.owned_here:
                code = sqlite.finalize(live.pop(statement.name))
                calls.append(CleanupCall("finalize", statement.name, code, bool(destructions)))

        require("live statements before close", sqlite.prepared_statements(connection), {item.value for item in live.values()})
        if flags["refresh"]:
            observed = sqlite.prepared_statements(connection)
        stale = not flags["refresh"] and (bool(fixture.statements) or flags["opaque_call"])
        refusal = None
        if policy == "checked_snapshot" and (stale or observed):
            refusal = "stale_snapshot" if stale else "nonempty_snapshot"
        else:
            deferred = policy == "defer_destroy"
            close = sqlite.close_v2 if deferred else sqlite.close
            code = close(connection)
            if code == OK:
                connection = None
            calls.append(CleanupCall("close_v2" if deferred else "close", None, code, bool(destructions)))

        phase = "open" if connection is not None else "destroyed" if destructions else "pending"
        result = CallBoundary(CleanupResult(True, phase, tuple(live), tuple(calls)), refusal)
        if connection is not None:
            require("returned connection is usable", sqlite.prepared_statements(connection), {item.value for item in live.values()})

        # These statements belong to owners outside the tested caller.
        for name in tuple(live):
            require("outside owner finalizes", sqlite.finalize(live.pop(name)), OK)
            require("destruction after outside finalization", len(destructions), int(connection is None and not live))
        if connection is not None:
            require("close by the next owner", sqlite.close(connection), OK)
            connection = None
        require("destruction by end of fixture", len(destructions), 1)
        return result
    finally:
        for handle in live.values():
            sqlite.finalize(handle)
        if connection is not None:
            sqlite.close(connection)


def main():
    sqlite = SQLiteProbe()
    print(f"SQLite {sqlite.version().decode('ascii')}")
    print(f"source ID: {sqlite.source_id().decode('ascii')}")
    checked = rejected = 0
    for fixture in fixtures():
        for policy in get_args(ClosePolicy):
            expected = compare(policy, fixture)
            if expected.result is None:
                rejected += 1
                continue
            actual = execute_native(sqlite, policy, fixture)
            require(f"{policy} at {fixture}", actual, expected)
            checked += 1
    print(f"Compared {checked} SQLite call boundaries. Source proof rejected {rejected} plans before execution.")


if __name__ == "__main__":
    main()
