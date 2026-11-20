"""Compare successful and error-returning SQLite backup finish on disposable data."""

from os import fsencode
from pathlib import Path
from tempfile import TemporaryDirectory

from rt04_sqlite_recovery import OK
from sqlite_backup_roles_probe import DONE, ROW, begin_backup, connections
from sqlite_cleanup_probe import BackupProbe, require


READONLY = 8


def probe_finish(sqlite, filename, *, read_only):
    with connections(sqlite, 1) as sources:
        source = sources[0]
        sqlite.step_once(source, b"CREATE TABLE copied (value INTEGER)", DONE)
        destructions, _marker, _destructor = sqlite.watch_destruction(source)
        destination = sqlite.connect_serialized(filename, read_only=read_only)
        backup = None
        try:
            backup = begin_backup(sqlite, source, destination)
            step_code = sqlite.backup_step(backup, -1)
            require("backup step", step_code, READONLY if read_only else DONE)
            require("close_v2 with live backup", sqlite.close_v2(source), OK)
            sources[0] = None
            require("source destruction before finish", len(destructions), 0)

            finish_code = sqlite.backup_finish(backup)
            backup = None
            require("finish diagnostic", finish_code, READONLY if read_only else OK)
            require("source destruction after finish", len(destructions), 1)
            table = b"fixed" if read_only else b"copied"
            sqlite.step_once(destination, b"SELECT count(*) FROM " + table, ROW)
        finally:
            if backup is not None:
                sqlite.backup_finish(backup)
            require("close destination after finish", sqlite.close(destination), OK)
    return step_code, finish_code


def main():
    sqlite = BackupProbe()
    print(f"SQLite {sqlite.version().decode('ascii')}")
    print(f"source ID: {sqlite.source_id().decode('ascii')}")
    with TemporaryDirectory(prefix="llmlang-backup-outcomes-") as directory:
        for read_only, name in ((False, "writable.sqlite"), (True, "read-only.sqlite")):
            filename = fsencode(Path(directory) / name)
            destination = sqlite.connect_serialized(filename)
            try:
                sqlite.step_once(destination, b"CREATE TABLE fixed (value INTEGER)", DONE)
            finally:
                require("close initialized destination", sqlite.close(destination), OK)
            step, finish = probe_finish(sqlite, filename, read_only=read_only)
            print(f"{name}: step={step}, finish={finish}, source destroyed at finish, destination usable after finish")


if __name__ == "__main__":
    main()
