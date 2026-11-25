#define _GNU_SOURCE
#include "bindings.h"

#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>

static void identify(const char *name, void *address) {
    Dl_info location;
    assert(dladdr(address, &location));
    printf("binding %s %s\n", name, location.dli_fname);
}

static const char *words[] = {
    "", "A", "a", "AB", "ab", "A1_", "a1_", "b", "B",
    "\xc3\x84", "\xc3\xa4", "\x7f",
};

int main(void) {
    identify("posix", (void *)(uintptr_t)&read);
    identify("sqlite", (void *)(uintptr_t)&sqlite3_stricmp);
    identify("openssl", (void *)(uintptr_t)&EVP_Digest);
    printf("sqlite_version %s\n", sqlite3_libversion());
    printf("openssl_version %s\n", OpenSSL_version(OPENSSL_VERSION));

    const size_t requests[] = {0, 1, 7, 16, 32, 33, 80};
    const size_t capacities[] = {0, 8, 32, 64};
    const unsigned char initial[] = "abcdefghijklmnopq";
    for (size_t i = 0; i < sizeof(requests) / sizeof(requests[0]); ++i) {
        for (size_t j = 0; j < sizeof(capacities) / sizeof(capacities[0]); ++j) {
            for (int valid = 0; valid <= 1; ++valid) {
                int descriptors[2];
                assert(pipe(descriptors) == 0);
                assert(write(descriptors[1], initial, sizeof(initial) - 1) == sizeof(initial) - 1);
                assert(close(descriptors[1]) == 0);
                unsigned char buffer[64] = {0};
                struct read_result result = checked_read(
                    valid ? descriptors[0] : -1, buffer, capacities[j], requests[i]);
                assert(close(descriptors[0]) == 0);
                printf("read %zu %zu %d %d %d %zu", requests[i], capacities[j], valid,
                       result.status, result.error, result.length);
                putchar(' ');
                for (size_t index = 0; index < result.length; ++index) {
                    printf("%02x", (unsigned int)buffer[index]);
                }
                puts("");
            }
        }
    }

    for (size_t i = 0; i < sizeof(words) / sizeof(words[0]); ++i) {
        for (size_t j = 0; j < sizeof(words) / sizeof(words[0]); ++j) {
            printf("compare %zu %zu %d\n", i, j, ascii_compare(words[i], words[j]));
        }
    }

    const size_t lengths[] = {0, 1, 2, 7, 32, 63, 64, 129, 256};
    for (size_t i = 0; i < sizeof(lengths) / sizeof(lengths[0]); ++i) {
        for (unsigned int salt = 0; salt <= 34; salt += 17) {
            unsigned char data[256], bytes[64];
            for (size_t j = 0; j < sizeof(data); ++j) {
                data[j] = (unsigned char)(j * 37 + salt);
            }
            unsigned int length = 0;
            int result = sha256_checked(data, lengths[i], bytes, &length);
            printf("digest %zu %u %d %u ", lengths[i], (unsigned int)salt, result, length);
            for (unsigned int j = 0; j < length; ++j) {
                printf("%02x", (unsigned int)bytes[j]);
            }
            puts("");
        }
    }
}
