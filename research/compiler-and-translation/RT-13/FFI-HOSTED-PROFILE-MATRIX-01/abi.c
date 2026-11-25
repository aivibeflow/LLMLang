typedef __UINT64_TYPE__ u64;
typedef __UINT32_TYPE__ u32;
typedef struct { u64 count; u32 flags; u32 reserved; } Pair;

_Static_assert(__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__, "target byte order");
_Static_assert(sizeof(void *) == 8 && _Alignof(void *) == 8, "target pointer width and alignment");
_Static_assert(sizeof(long) == EXPECT_LONG, "target long width");
_Static_assert(sizeof(Pair) == 16 && _Alignof(Pair) == 8, "target record layout");
_Static_assert(__builtin_offsetof(Pair, flags) == 8, "target field layout");

Pair roundtrip(Pair input, unsigned flag) {
    input.flags ^= flag;
    return input;
}
