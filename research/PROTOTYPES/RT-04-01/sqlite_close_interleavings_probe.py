"""Run the close interleavings against a serialized, in-memory SQLite connection."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Event, RLock

from rt04_close_interleavings import Observation, Schedule, predict, schedules
from rt04_sqlite_recovery import OK
from sqlite_cleanup_probe import SQLiteProbe, require


WAIT_SECONDS = 5


def execute(sqlite: SQLiteProbe, schedule: Schedule) -> Observation:
    """Use explicit rendezvous to put prepare at the selected boundary."""
    connection = sqlite.connect_serialized()
    statement = None
    version = 0
    guard = RLock()
    producer_guard = RLock() if schedule.policy == "alias_guard" else guard
    contended = Event()

    def prepare(*, expect_contention=False):
        nonlocal statement, version
        if expect_contention:
            if producer_guard.acquire(blocking=False):
                producer_guard.release()
                raise RuntimeError("the producer could enter the guarded close")
            contended.set()
        with producer_guard:
            if connection is None:
                return False
            statement = sqlite.prepare(connection)
            version += 1
            return True

    try:
        destructions, _marker, _destructor = sqlite.watch_destruction(connection)
        with ThreadPoolExecutor(max_workers=1) as pool:
            location = schedule.prepare_at
            if location == "before_snapshot":
                prepared = pool.submit(prepare).result(timeout=WAIT_SECONDS)

            exclusive = schedule.policy in ("shared_guard", "alias_guard")
            queued = None
            with guard if exclusive else nullcontext():
                with guard:
                    seen = len(sqlite.prepared_statements(connection))
                    seen_version = version
                if location == "after_snapshot":
                    prepared = pool.submit(prepare).result(timeout=WAIT_SECONDS)

                validated = None
                if seen == 0 and schedule.policy == "split_version":
                    with guard:
                        validated = seen_version == version
                if location == "after_validation":
                    prepared = pool.submit(prepare).result(timeout=WAIT_SECONDS)

                if exclusive and location == "after_close":
                    queued = pool.submit(prepare, expect_contention=True)
                    if not contended.wait(WAIT_SECONDS):
                        raise RuntimeError("the producer did not contend for the guard")

                code = None
                if seen == 0 and validated is not False:
                    with guard:
                        code = sqlite.close(connection)
                        if code == OK:
                            connection = None

            if location == "after_close":
                if queued is None:
                    queued = pool.submit(prepare)
                prepared = queued.result(timeout=WAIT_SECONDS)

        require("destruction at return", len(destructions), int(connection is None))
        if connection is not None:
            expected_statements = {statement.value} if statement is not None else set()
            require("remaining statements", sqlite.prepared_statements(connection), expected_statements)
    finally:
        if statement is not None:
            require("finalize producer statement", sqlite.finalize(statement), OK)
        if connection is not None:
            require("close remaining connection", sqlite.close(connection), OK)

    require("destruction by end of fixture", len(destructions), 1)
    return Observation(seen, validated, code, prepared)


def main():
    sqlite = SQLiteProbe()
    print(f"SQLite {sqlite.version().decode('ascii')}")
    print(f"source ID: {sqlite.source_id().decode('ascii')}")
    for schedule in schedules():
        actual = execute(sqlite, schedule)
        require(schedule, actual, predict(schedule))
        print(f"{schedule.policy}, {schedule.prepare_at}: {actual}")


if __name__ == "__main__":
    main()
