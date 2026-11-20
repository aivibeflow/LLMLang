"""Check role overlap and rejected backup initialization on SQLite."""

from contextlib import contextmanager
from itertools import permutations, product

from rt04_sqlite_recovery import ERROR, OK
from sqlite_cleanup_probe import BackupProbe, require


ROW = 100
DONE = 101


@contextmanager
def connections(sqlite, count):
    handles = []
    try:
        for _ in range(count):
            handles.append(sqlite.connect_serialized())
        yield handles
    finally:
        for handle in reversed(handles):
            if handle is not None:
                require("close fixture connection", sqlite.close(handle), OK)


def begin_backup(sqlite, source, destination):
    backup = sqlite.backup_init(destination, b"main", source, b"main")
    require("initialize backup", bool(backup), True)
    return backup


def probe_shared_source(sqlite, roles, reverse):
    source_slot, first_destination, second_destination = roles
    with connections(sqlite, 3) as handles:
        source = handles[source_slot]
        destructions, _marker, _destructor = sqlite.watch_destruction(source)
        pending = []
        try:
            for slot in (first_destination, second_destination):
                pending.append(begin_backup(sqlite, source, handles[slot]))
                sqlite.step_once(source, b"SELECT 1", ROW)

            require("retire shared source", sqlite.close_v2(source), OK)
            handles[source_slot] = None
            require("source destruction with two backups", len(destructions), 0)
            if reverse:
                pending.reverse()
            while pending:
                require("finish shared-source backup", sqlite.backup_finish(pending.pop(0)), OK)
                require("source destruction after finishing", len(destructions), int(not pending))
        finally:
            for backup in pending:
                require("finish remaining backup", sqlite.backup_finish(backup), OK)


def require_rejected_init(sqlite, source, destination):
    backup = sqlite.backup_init(destination, b"main", source, b"main")
    if backup:
        sqlite.backup_finish(backup)
        raise RuntimeError("the fixture unexpectedly admitted backup_init")
    require("backup initialization error", sqlite.error_code(destination), ERROR)


def probe_failed_init(sqlite, transaction):
    with connections(sqlite, 2) as handles:
        source, destination = handles
        if transaction == "read":
            sqlite.step_once(destination, b"CREATE TABLE fixture (v INTEGER)", DONE)
            sqlite.step_once(destination, b"INSERT INTO fixture VALUES (1)", DONE)
            sqlite.step_once(destination, b"BEGIN", DONE)
            sqlite.step_once(destination, b"SELECT v FROM fixture", ROW)
        else:
            sqlite.step_once(destination, b"BEGIN IMMEDIATE", DONE)
        require_rejected_init(sqlite, source, destination)
        sqlite.step_once(destination, b"ROLLBACK", DONE)

        # Both connections can participate in a new backup after rollback.
        backup = begin_backup(sqlite, source, destination)
        require("finish retry", sqlite.backup_finish(backup), OK)
        require("source closes after failed start and retry", sqlite.close(source), OK)
        handles[0] = None


def main():
    sqlite = BackupProbe()
    print(f"SQLite {sqlite.version().decode('ascii')}")
    print(f"source ID: {sqlite.source_id().decode('ascii')}")
    shared = 0
    for roles, reverse in product(permutations(range(3)), (False, True)):
        probe_shared_source(sqlite, roles, reverse)
        shared += 1
    with connections(sqlite, 1) as (connection,):
        require_rejected_init(sqlite, connection, connection)
    for transaction in ("read", "write"):
        probe_failed_init(sqlite, transaction)
    print(f"{shared} shared-source traces, one same-identity rejection, two transaction failures with successful retry")


if __name__ == "__main__":
    main()
