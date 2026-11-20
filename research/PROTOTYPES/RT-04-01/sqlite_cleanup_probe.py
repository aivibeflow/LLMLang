"""Probe three SQLite cleanup contracts using in-memory databases only."""

from ctypes import CDLL, CFUNCTYPE, POINTER, byref, c_char_p, c_int, c_void_p
from ctypes.util import find_library


OK, ERROR, BUSY = 0, 1, 5
UTF8 = 1
ScalarFunction = CFUNCTYPE(None, c_void_p, c_int, POINTER(c_void_p))
Destructor = CFUNCTYPE(None, c_void_p)


def require(label, actual, expected):
    if actual != expected:
        raise RuntimeError(f"{label}: got {actual}, expected {expected}")


def record(label, actual, expected):
    require(label, actual, expected)
    print(f"{label} = {actual}")


def main():
    name = find_library("sqlite3")
    if name is None:
        raise SystemExit("The probe requires the SQLite shared library")
    library = CDLL(name)

    def bind(symbol, result, *arguments):
        function = getattr(library, "sqlite3_" + symbol)
        function.argtypes = arguments
        function.restype = result
        return function

    version = bind("libversion", c_char_p)
    source_id = bind("sourceid", c_char_p)
    open_connection = bind("open", c_int, c_char_p, POINTER(c_void_p))
    prepare_statement = bind("prepare_v2", c_int, c_void_p, c_char_p, c_int, POINTER(c_void_p), POINTER(c_char_p))
    step = bind("step", c_int, c_void_p)
    finalize = bind("finalize", c_int, c_void_p)
    close = bind("close", c_int, c_void_p)
    close_v2 = bind("close_v2", c_int, c_void_p)
    create_function = bind(
        "create_function_v2", c_int, c_void_p, c_char_p, c_int, c_int, c_void_p,
        ScalarFunction, c_void_p, c_void_p, Destructor,
    )
    result_null = bind("result_null", None, c_void_p)

    def connect():
        connection = c_void_p()
        require("open memory database", open_connection(b":memory:", byref(connection)), OK)
        return connection

    def prepare(connection, sql=b"SELECT 1"):
        statement = c_void_p()
        require("prepare statement", prepare_statement(connection, sql, -1, byref(statement), None), OK)
        return statement

    print(f"SQLite {version().decode('ascii')}")
    print(f"source ID: {source_id().decode('ascii')}")

    connection = connect()
    pending = prepare(connection)
    record("close with pending statement", close(connection), BUSY)
    other = prepare(connection, b"SELECT 2")
    record("finalize statement prepared after busy close", finalize(other), OK)
    record("finalize original statement", finalize(pending), OK)
    record("close after finalizing statements", close(connection), OK)

    connection = connect()
    statement = prepare(connection, b"SELECT abs(-9223372036854775808)")
    record("step with integer overflow", step(statement), ERROR)
    record("finalize after step error", finalize(statement), ERROR)
    record("close after finalize error", close(connection), OK)

    connection = connect()
    destructions = []

    @ScalarFunction
    def marker(context, _argc, _argv):
        result_null(context)

    @Destructor
    def observe_destruction(_data):
        destructions.append("destroyed")

    require("register connection marker", create_function(
        connection, b"llmlang_marker", 0, UTF8, None, marker, None, None, observe_destruction,
    ), OK)
    pending = prepare(connection)
    record("close_v2 with pending statement", close_v2(connection), OK)
    record("destructor count after close_v2", len(destructions), 0)
    # After close_v2 the connection pointer is unusable. Finalize only the statement.
    record("finalize pending statement after close_v2", finalize(pending), OK)
    record("destructor count after finalization", len(destructions), 1)


if __name__ == "__main__":
    main()
