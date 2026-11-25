typedef unsigned long long u64;
typedef __UINTPTR_TYPE__ address;

_Static_assert(sizeof(address) == 8, "require wasm64 addresses");

int view_byte(u64 base, u64 span, u64 offset) {
#ifdef NARROW_32
    base = (unsigned int)base;
    span = (unsigned int)span;
    offset = (unsigned int)offset;
#endif
    const u64 capacity = (u64)__builtin_wasm_memory_size(0) * 65536;
#ifdef ADD_END
    if (offset >= span || base + span > capacity)
        return -1;
#else
    if (offset >= span || base > capacity || span > capacity - base)
        return -1;
#endif
    return *(const unsigned char *)(address)(base + offset);
}
