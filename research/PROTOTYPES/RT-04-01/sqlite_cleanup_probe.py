"""Probe SQLite cleanup contracts using in-memory databases only."""

from argparse import ArgumentParser
from ctypes import CDLL, CFUNCTYPE, POINTER, byref, c_char_p, c_int, c_void_p
from ctypes.util import find_library
from itertools import product
from typing import get_args

from rt04_sqlite_recovery import BUSY, ERROR, OK, Policy, cleanup, statement_fixtures


UTF8 = 1
OPEN_READWRITE = 0x00000002
OPEN_CREATE = 0x00000004
OPEN_FULLMUTEX = 0x00010000
ScalarFunction = CFUNCTYPE(None, c_void_p, c_int, POINTER(c_void_p))
Destructor = CFUNCTYPE(None, c_void_p)


def require(label, actual, expected):
    if actual != expected:
        raise RuntimeError(f"{label}: got {actual}, expected {expected}")


def record(label, actual, expected):
    require(label, actual, expected)
    print(f"{label} = {actual}")


class SQLiteProbe:
    def __init__(self):
        name = find_library("sqlite3")
        if name is None:
            raise SystemExit("The probe requires the SQLite shared library")
        self._library = CDLL(name)
        bind = self.bind

        self.version = bind("libversion", c_char_p)
        self.source_id = bind("sourceid", c_char_p)
        self.open_connection = bind("open", c_int, c_char_p, POINTER(c_void_p))
        self.open_v2 = bind("open_v2", c_int, c_char_p, POINTER(c_void_p), c_int, c_char_p)
        self.connection_mutex = bind("db_mutex", c_void_p, c_void_p)
        self.prepare_statement = bind(
            "prepare_v2", c_int, c_void_p, c_char_p, c_int, POINTER(c_void_p), POINTER(c_char_p),
        )
        self.step = bind("step", c_int, c_void_p)
        self.next_statement = bind("next_stmt", c_void_p, c_void_p, c_void_p)
        self.finalize = bind("finalize", c_int, c_void_p)
        self.close = bind("close", c_int, c_void_p)
        self.close_v2 = bind("close_v2", c_int, c_void_p)
        self.create_function = bind(
            "create_function_v2", c_int, c_void_p, c_char_p, c_int, c_int, c_void_p,
            ScalarFunction, c_void_p, c_void_p, Destructor,
        )
        self.result_null = bind("result_null", None, c_void_p)

    def bind(self, symbol, result, *arguments):
        function = getattr(self._library, "sqlite3_" + symbol)
        function.argtypes = arguments
        function.restype = result
        return function

    def connect(self):
        connection = c_void_p()
        require("open memory database", self.open_connection(b":memory:", byref(connection)), OK)
        return connection

    def connect_serialized(self):
        connection = c_void_p()
        flags = OPEN_READWRITE | OPEN_CREATE | OPEN_FULLMUTEX
        code = self.open_v2(b":memory:", byref(connection), flags, None)
        if code != OK and connection:
            self.close(connection)
        require("open serialized memory database", code, OK)
        if not self.connection_mutex(connection):
            self.close(connection)
            raise RuntimeError("SQLite did not provide a connection mutex")
        return connection

    def prepare(self, connection, sql=b"SELECT 1"):
        statement = c_void_p()
        require("prepare statement", self.prepare_statement(connection, sql, -1, byref(statement), None), OK)
        return statement

    def step_once(self, connection, sql, expected):
        statement = self.prepare(connection, sql)
        code = self.step(statement)
        finalized = self.finalize(statement)
        require("step fixture statement", code, expected)
        require("finalize fixture statement", finalized, OK)

    def prepared_statements(self, connection):
        statements = set()
        handle = self.next_statement(connection, None)
        while handle is not None:
            statements.add(handle)
            handle = self.next_statement(connection, handle)
        return statements

    def watch_destruction(self, connection):
        destructions = []

        @ScalarFunction
        def marker(context, _argc, _argv):
            self.result_null(context)

        @Destructor
        def observe_destruction(_data):
            destructions.append("destroyed")

        require("register connection marker", self.create_function(
            connection, b"llmlang_marker", 0, UTF8, None, marker, None, None, observe_destruction,
        ), OK)
        # Keep both C callbacks alive until SQLite has destroyed the connection.
        return destructions, marker, observe_destruction


class BackupProbe(SQLiteProbe):
    def __init__(self):
        super().__init__()
        self.backup_init = self.bind("backup_init", c_void_p, c_void_p, c_char_p, c_void_p, c_char_p)
        self.backup_finish = self.bind("backup_finish", c_int, c_void_p)
        self.error_code = self.bind("errcode", c_int, c_void_p)


def probe_contracts(sqlite):
    connection = sqlite.connect()
    pending = sqlite.prepare(connection)
    record("close with pending statement", sqlite.close(connection), BUSY)
    other = sqlite.prepare(connection, b"SELECT 2")
    record("finalize statement prepared after busy close", sqlite.finalize(other), OK)
    record("finalize original statement", sqlite.finalize(pending), OK)
    record("close after finalizing statements", sqlite.close(connection), OK)

    connection = sqlite.connect()
    statement = sqlite.prepare(connection, b"SELECT abs(-9223372036854775808)")
    record("step with integer overflow", sqlite.step(statement), ERROR)
    record("finalize after step error", sqlite.finalize(statement), ERROR)
    record("close after finalize error", sqlite.close(connection), OK)

    connection = sqlite.connect()
    destructions, _marker, _destructor = sqlite.watch_destruction(connection)
    pending = sqlite.prepare(connection)
    record("close_v2 with pending statement", sqlite.close_v2(connection), OK)
    record("destructor count after close_v2", len(destructions), 0)
    # After close_v2 the connection pointer is unusable. Finalize only the statement.
    record("finalize pending statement after close_v2", sqlite.finalize(pending), OK)
    record("destructor count after finalization", len(destructions), 1)


def probe_recovery_trace(sqlite, statements, expected):
    connection = sqlite.connect()
    destructions, _marker, _destructor = sqlite.watch_destruction(connection)
    live = {}
    for statement in statements:
        sql = b"SELECT abs(-9223372036854775808)" if statement.failed_step else b"SELECT 1"
        handle = sqlite.prepare(connection, sql)
        if statement.failed_step:
            require("step with integer overflow", sqlite.step(handle), ERROR)
        live[statement.name] = handle

    require("SQLite statement set at entry", sqlite.prepared_statements(connection), {handle.value for handle in live.values()})

    for call in expected.calls:
        if call.operation == "finalize":
            code = sqlite.finalize(live.pop(call.statement))
        else:
            if connection is None:
                raise RuntimeError("the model attempted to close an invalidated connection")
            close = sqlite.close_v2 if call.operation == "close_v2" else sqlite.close
            code = close(connection)
            if code == OK:
                connection = None
        require(call.operation, code, call.code)
        require("destructor count at return", len(destructions), int(call.destroyed))
        if connection is not None:
            require("SQLite statement set", sqlite.prepared_statements(connection), {handle.value for handle in live.values()})

    require("remaining statements", tuple(live), expected.remaining_statements)
    require("forwarded live connection", connection is not None, expected.forwards_connection)

    # Complete the fixture as the owners outside the caller would. This tail
    # verifies the pending destruction on their last finalize and frees all handles.
    for statement in statements:
        if statement.name in live:
            code = sqlite.finalize(live.pop(statement.name))
            require("finalize outside caller", code, ERROR if statement.failed_step else OK)
            require("destructor count outside caller", len(destructions), int(connection is None and not live))
    if connection is not None:
        require("close after external finalization", sqlite.close(connection), OK)
    require("destructor count at end", len(destructions), 1)


def probe_recovery_matrix(sqlite):
    compared = rejected = 0
    for statements, policy, close_first in product(statement_fixtures(), get_args(Policy), (True, False)):
        result = cleanup(policy, statements, close_first=close_first)
        if not result.accepted:
            rejected += 1
            continue
        try:
            probe_recovery_trace(sqlite, statements, result)
        except (KeyError, RuntimeError) as exc:
            raise RuntimeError(f"{policy}, close_first={close_first}, {statements}: {exc}") from exc
        compared += 1
    print(f"Compared {compared} admitted traces with SQLite and skipped {rejected} rejected plans")


def probe_snapshot_freshness(sqlite):
    connection = sqlite.connect()
    record("initial statement count", len(sqlite.prepared_statements(connection)), 0)
    record("close with unchanged empty set", sqlite.close(connection), OK)

    connection = sqlite.connect()
    record("statement count when snapshot was captured", len(sqlite.prepared_statements(connection)), 0)
    statement = sqlite.prepare(connection)
    record("statement count after an intervening prepare", len(sqlite.prepared_statements(connection)), 1)
    record("close after relying on a stale snapshot", sqlite.close(connection), BUSY)
    record("finalize intervening statement", sqlite.finalize(statement), OK)
    record("statement count after refreshing the snapshot", len(sqlite.prepared_statements(connection)), 0)
    record("close after refreshing the snapshot", sqlite.close(connection), OK)


def main():
    parser = ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--recovery-matrix", action="store_true", help="compare the bounded model with SQLite")
    modes.add_argument("--snapshot-freshness", action="store_true", help="check whether an older empty list suffices")
    args = parser.parse_args()
    sqlite = SQLiteProbe()
    print(f"SQLite {sqlite.version().decode('ascii')}")
    print(f"source ID: {sqlite.source_id().decode('ascii')}")
    if args.recovery_matrix:
        probe_recovery_matrix(sqlite)
    elif args.snapshot_freshness:
        probe_snapshot_freshness(sqlite)
    else:
        probe_contracts(sqlite)


if __name__ == "__main__":
    main()
