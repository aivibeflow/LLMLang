import ctypes as c
import sys

provider = c.CDLL(sys.argv[1])
step = provider.checked_add
step.argtypes = (c.c_uint64, c.c_uint32, c.POINTER(c.c_uint64))
step.restype = c.c_uint32
for row in sys.stdin:
    value, enabled = map(int, row.split())
    slot = c.c_uint64(0xabad1234abcdef01)
    print(step(value, enabled, c.byref(slot)), slot.value)
