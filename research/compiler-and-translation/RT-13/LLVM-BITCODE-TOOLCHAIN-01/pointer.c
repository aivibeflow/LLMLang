typedef unsigned int u32;

u32 transform(const u32 *input) {
    return (*input ^ 0x5a5a5a5au) + 1u;
}
