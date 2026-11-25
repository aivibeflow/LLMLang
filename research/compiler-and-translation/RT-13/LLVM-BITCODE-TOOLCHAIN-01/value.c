typedef unsigned int u32;

u32 transform(u32 input) {
#ifdef ALTER_SEMANTICS
    return (input ^ 0x5a5a5a5au) + 3u;
#else
    return (input ^ 0x5a5a5a5au) + 1u;
#endif
}
