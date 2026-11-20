"""Observe reentrant prepare and dependent lifetimes on in-memory SQLite."""

from ctypes import POINTER, byref, c_char_p, c_int, c_int64, c_void_p
from threading import RLock

from rt04_close_reentry import (
    CallbackCase, CallbackObservation, CloseCall, CoverageObservation, Dependent,
    callback_cases, coverage_cases, predict_callback, predict_coverage,
)
from rt04_sqlite_recovery import OK
from sqlite_cleanup_probe import Destructor, SQLiteProbe, ScalarFunction, UTF8, require


ROW = 100
DONE = 101


class CloseProbe(SQLiteProbe):
    def __init__(self):
        super().__init__()
        self.blob_open = self.bind(
            "blob_open", c_int, c_void_p, c_char_p, c_char_p, c_char_p, c_int64, c_int, POINTER(c_void_p),
        )
        self.blob_close = self.bind("blob_close", c_int, c_void_p)
        self.backup_init = self.bind("backup_init", c_void_p, c_void_p, c_char_p, c_void_p, c_char_p)
        self.backup_finish = self.bind("backup_finish", c_int, c_void_p)


def step_once(sqlite: SQLiteProbe, connection, sql, expected):
    statement = sqlite.prepare(connection, sql)
    code = sqlite.step(statement)
    finalized = sqlite.finalize(statement)
    require("step fixture statement", code, expected)
    require("finalize fixture statement", finalized, OK)


def run_callback(sqlite: SQLiteProbe, case: CallbackCase) -> CallbackObservation:
    connection = sqlite.connect_serialized()
    lock = RLock()
    retained = None
    existing = None
    reserved = False
    actions = []
    errors = []

    def try_prepare():
        with lock:
            if reserved or connection is None:
                return None
            return sqlite.prepare(connection)

    @ScalarFunction
    def callback(context, _argc, _argv):
        nonlocal retained
        try:
            if not case.callback_prepares:
                actions.append("preserved")
            else:
                retained = try_prepare()
                actions.append("refused" if retained is None else "retained")
        except Exception as exc:
            errors.append(exc)
        sqlite.result_null(context)

    try:
        destroyed, _marker, _destructor = sqlite.watch_destruction(connection)
        require("register fixture callback", sqlite.create_function(
            connection, b"llmlang_callback", 0, UTF8, None, callback, None, None, Destructor(),
        ), OK)
        if case.initially_live:
            existing = sqlite.prepare(connection)

        with lock:
            reserved = case.policy == "reserve_close"
            initial_count = len(sqlite.prepared_statements(connection))
            after = initial_count
            close_code = None
            action = "skipped"
            if initial_count == 0:
                step_once(sqlite, connection, b"SELECT llmlang_callback()", ROW)
                if errors:
                    raise RuntimeError("fixture callback failed") from errors[0]
                require("callback calls", len(actions), 1)
                action = actions[0]
                after = len(sqlite.prepared_statements(connection))
                if case.policy != "inspect_again" or after == 0:
                    close_code = sqlite.close(connection)
                    if close_code == OK:
                        connection = None
            reserved = False

        require("destruction at return", len(destroyed), int(connection is None))
        probe = try_prepare()
        if probe is not None:
            require("finalize statement after wrapper return", sqlite.finalize(probe), OK)
        require("prepare through the wrapper after return", probe is not None, connection is not None)
        if connection is not None:
            expected = {handle.value for handle in (retained, existing) if handle is not None}
            require("retained statement set", sqlite.prepared_statements(connection), expected)
    finally:
        for handle in (retained, existing):
            if handle is not None:
                require("finalize persistent statement", sqlite.finalize(handle), OK)
        if connection is not None:
            require("close retained connection", sqlite.close(connection), OK)

    require("destruction by end of fixture", len(destroyed), 1)
    return CallbackObservation(initial_count, action, after, close_code)


def run_coverage(sqlite: CloseProbe, kind: Dependent, operation: CloseCall) -> CoverageObservation:
    connection = sqlite.connect_serialized()
    destination = None
    dependent = None
    release = sqlite.finalize
    try:
        destroyed, _marker, _destructor = sqlite.watch_destruction(connection)
        if kind == "statement":
            dependent = sqlite.prepare(connection)
        elif kind == "blob":
            step_once(sqlite, connection, b"CREATE TABLE fixture (payload BLOB)", DONE)
            step_once(sqlite, connection, b"INSERT INTO fixture VALUES (zeroblob(4))", DONE)
            release = sqlite.blob_close
            dependent = c_void_p()
            require("open blob", sqlite.blob_open(
                connection, b"main", b"fixture", b"payload", 1, 0, byref(dependent),
            ), OK)
        elif kind == "backup":
            destination = sqlite.connect_serialized()
            release = sqlite.backup_finish
            dependent = sqlite.backup_init(destination, b"main", connection, b"main")
            require("backup created", bool(dependent), True)

        count = len(sqlite.prepared_statements(connection))
        close = sqlite.close_v2 if operation == "close_v2" else sqlite.close
        code = close(connection)
        if code == OK:
            connection = None
        at_close = bool(destroyed)
        if dependent:
            release_code = release(dependent)
            dependent = None
            require("release live dependent", release_code, OK)
        after_release = bool(destroyed)
    finally:
        if dependent:
            require("release remaining dependent", release(dependent), OK)
        if destination is not None:
            require("close backup destination after finish", sqlite.close(destination), OK)
        if connection is not None:
            require("close retained connection", sqlite.close(connection), OK)

    require("destruction by end of fixture", len(destroyed), 1)
    return CoverageObservation(count, code, at_close, after_release)


def main():
    sqlite = CloseProbe()
    print(f"SQLite {sqlite.version().decode('ascii')}")
    print(f"source ID: {sqlite.source_id().decode('ascii')}")
    for case in callback_cases():
        actual = run_callback(sqlite, case)
        require(case, actual, predict_callback(case))
        print(f"{case}: {actual}")
    for kind, operation in coverage_cases():
        actual = run_coverage(sqlite, kind, operation)
        require((kind, operation), actual, predict_coverage(kind, operation))
        print(f"{kind}, {operation}: {actual}")


if __name__ == "__main__":
    main()
