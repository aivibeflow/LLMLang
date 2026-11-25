"""Dafny Python extern binding for one selected C lookup provider."""

import ctypes

_bound = None
_signed_result = False


def configure(library, symbol, *, signed_result=False):
    global _bound, _signed_result
    _bound = getattr(ctypes.CDLL(str(library)), symbol)
    _bound.argtypes = (ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64,
                       ctypes.POINTER(ctypes.c_uint64))
    _bound.restype = ctypes.c_uint32
    _signed_result = signed_result


class default__:
    @staticmethod
    def resolve(base, count, slot):
        out = ctypes.c_uint64(0xCAFE)
        tag = _bound(base, count, slot, ctypes.byref(out))
        value = ctypes.c_int64(out.value).value if _signed_result else out.value
        return tag, value
