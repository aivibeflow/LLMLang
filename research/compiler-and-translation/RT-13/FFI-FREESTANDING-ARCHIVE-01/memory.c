typedef __SIZE_TYPE__ size_type;

void *memcpy(void *destination, const void *source, size_type count) {
    unsigned char *to = destination;
    const unsigned char *from = source;
    for (size_type index = 0; index < count; ++index) {
        to[index] = from[index];
    }
    return destination;
}
