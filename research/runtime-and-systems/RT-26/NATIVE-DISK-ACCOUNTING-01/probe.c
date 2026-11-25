#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <fcntl.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>

static void checkpoint(void) {
    assert(raise(SIGSTOP) == 0);
}

int main(void) {
    int fd = open("fixture-file", O_CREAT | O_EXCL | O_RDWR, 0600);
    assert(fd >= 0);
    assert(ftruncate(fd, 32768) == 0);
    unsigned char page[8192];
    memset(page, 0x47, sizeof(page));

    checkpoint();
    assert(pwrite(fd, page, 4096, 4096) == 4096);
    checkpoint();
    memset(page, 0, sizeof(page));
    assert(pread(fd, page, 4096, 4096) == 4096);
    for (int i = 0; i < 4096; ++i)
        assert(page[i] == 0x47);
    checkpoint();
    memset(page, 0x47, sizeof(page));
    assert(pread(fd, page, sizeof(page), 16384) == (ssize_t)sizeof(page));
    for (size_t i = 0; i < sizeof(page); ++i)
        assert(page[i] == 0);
    checkpoint();
    assert(fsync(fd) == 0);
    checkpoint();
    memset(page, 0x51, 512);
    assert(pwrite(fd, page, 512, 128) == 512);
    assert(pwrite(fd, page, 512, 128) == 512);
    checkpoint();
    assert(ftruncate(fd, 0) == 0);
    checkpoint();
    assert(close(fd) == 0);
    assert(unlink("fixture-file") == 0);
    return 0;
}
