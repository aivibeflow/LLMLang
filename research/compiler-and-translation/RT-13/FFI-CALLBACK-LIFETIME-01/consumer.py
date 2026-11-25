"""Exercise CPython ctypes upcalls from the shared native provider."""
from ctypes import CDLL, CFUNCTYPE, POINTER, byref, cast, c_int, c_uint64, c_void_p
import sys
import threading


def main():
    library = CDLL(sys.argv[1])
    payload, profile, offset = map(int, sys.argv[2:])
    upcall = CFUNCTYPE(c_int, c_void_p, c_uint64, c_int, c_void_p)
    library.fixture_thread.argtypes = [c_void_p, c_uint64, POINTER(c_int)]
    library.fixture_retire.argtypes = [c_void_p, c_uint64]
    library.fixture_finish.argtypes = [c_void_p, c_uint64, POINTER(c_int)]
    library.fixture_drive.argtypes = [upcall, c_void_p, c_void_p, c_int, c_int]
    owner = threading.get_ident()
    primary, peer = c_int(offset), c_int(offset + 7)

    @upcall
    def callback(session, ticket, value, context):
        kind, ignored = c_int(), c_int()
        if (library.fixture_thread(session, ticket, byref(kind)) != 0
                or library.fixture_retire(session, ticket) != 2
                or library.fixture_finish(session, ticket, byref(ignored)) != 2):
            return -88
        expected = 1 if threading.get_ident() == owner else 2
        if kind.value != expected:
            return -88
        try:
            if value == -7:
                raise ValueError("fixture callback failed")
            return kind.value * 1000 + value * 3 + cast(context, POINTER(c_int)).contents.value
        except ValueError:
            return -77

    return library.fixture_drive(callback, byref(primary), byref(peer), payload, profile)


if __name__ == "__main__":
    sys.exit(main())
