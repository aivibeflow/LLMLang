typedef unsigned char u8;
typedef unsigned int u32;

struct iovec {
    const u8 *base;
    u32 length;
};

__attribute__((import_module("wasi_snapshot_preview1"), import_name("fd_write")))
extern u32 fd_write(u32 fd, const struct iovec *vectors, u32 count, u32 *written);

static u32 ready;

void _initialize(void) {
    ready = 1;
}

u32 emit(u32 fd, u32 left, u32 right, u32 seed) {
    if (!ready) {
        return 253u << 16;
    }
    if (left > 8 || right > 8) {
        return 255u << 16;
    }
    u8 a[8], b[8];
    for (u32 i = 0; i < 8; ++i) {
        a[i] = (u8)(seed + i);
        b[i] = (u8)(seed + 32 + i);
    }
    const struct iovec vectors[2] = {{a, left}, {b, right}};
    u32 written = 0;
    const u32 status = fd_write(fd, vectors, 2, &written);
    if (status != 0) {
        return status << 16;
    }
    if (written > left + right) {
        return 254u << 16;
    }
    return written;
}
