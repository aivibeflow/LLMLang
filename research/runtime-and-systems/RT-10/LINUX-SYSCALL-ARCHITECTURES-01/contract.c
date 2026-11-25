extern long raw_read(long descriptor, unsigned char *target, long length);
extern long raw_write(long descriptor, const char *source, long length);

static long record(char *output, const unsigned char *input, long count)
{
    const char digits[] = "0123456789abcdef";
    output[0] = (char)('0' + count);
    output[1] = ':';
    for (long i = 0; i < count; ++i) {
        output[2 + i * 2] = digits[input[i] >> 4];
        output[3 + i * 2] = digits[input[i] & 15];
    }
    output[2 + count * 2] = '\n';
    return 3 + count * 2;
}

int run_contract(void)
{
    unsigned char bytes[4] = {254, 254, 254, 254};
    char transcript[64];
    if (raw_read(-1, bytes, 4) != -9 || raw_read(0, bytes, 0) != 0)
        return 1;
    for (long i = 0; i < 4; ++i) {
        if (bytes[i] != 254)
            return 2;
    }
    transcript[0] = 'B';
    transcript[1] = 'Z';
    transcript[2] = '\n';
    long used = 3;
    for (long i = 0; i < 3; ++i) {
        for (long j = 0; j < 4; ++j)
            bytes[j] = 254;
        long count = raw_read(0, bytes, 4);
        if (count < 0 || count > 4)
            return 3;
        for (long j = count; j < 4; ++j) {
            if (bytes[j] != 254)
                return 4;
        }
        used += record(transcript + used, bytes, count);
        if (count == 0)
            return raw_write(1, transcript, used) == used ? 0 : 5;
    }
    return 6;
}
