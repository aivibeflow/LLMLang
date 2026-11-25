#define _GNU_SOURCE
#include <dlfcn.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern const void *rust_system_malloc_address(void);
extern uint8_t *rust_buffer_allocate(size_t);
extern void rust_buffer_release(uint8_t *, size_t);
extern uint64_t rust_borrow_digest(const uint8_t *, size_t);

enum { OK, CLOSED, WRONG_OWNER, SHORT };
typedef uint8_t *(*allocate_fn)(size_t);
typedef void (*release_fn)(uint8_t *, size_t);

struct owner {
    const char *name;
    allocate_fn allocate;
    release_fn release;
    unsigned releases;
};

struct buffer {
    uint8_t *bytes;
    size_t len;
    struct owner *owner;
};

static void *(*mi_malloc)(size_t);
static void (*mi_free)(void *);

static void check(int condition, const char *message) {
    if (!condition) {
        fprintf(stderr, "%s\n", message);
        exit(1);
    }
}

static uint8_t *mi_allocate(size_t len) {
    return mi_malloc(len);
}

static void mi_release(uint8_t *bytes, size_t len) {
    (void)len;
    mi_free(bytes);
}

static struct buffer create(struct owner *owner, size_t len) {
    check(len > 0, "empty buffer");
    struct buffer value = {owner->allocate(len), len, owner};
    check(value.bytes != NULL, "allocation failed");
    return value;
}

static int release_as(struct buffer *value, struct owner *requested) {
    if (value->bytes == NULL)
        return CLOSED;
    if (requested != value->owner)
        return WRONG_OWNER;
    value->owner->release(value->bytes, value->len);
    value->owner->releases++;
    value->bytes = NULL;
    return OK;
}

static int copy_into(const struct buffer *value, uint8_t *out, size_t capacity) {
    if (value->bytes == NULL)
        return CLOSED;
    if (capacity < value->len)
        return SHORT;
    memcpy(out, value->bytes, value->len);
    return OK;
}

static uint64_t digest(const uint8_t *bytes, size_t len) {
    uint64_t result = 0;
    for (size_t i = 0; i < len; i++)
        result = result * 131 + bytes[i];
    return result;
}

static uint8_t pattern(size_t index, unsigned salt) {
    return (uint8_t)((index * 193 + salt) & 255);
}

static void trial(struct owner *owner, struct owner *other, size_t len, unsigned salt) {
    struct buffer source = create(owner, len);
    struct buffer destination = create(other, len);
    const unsigned source_releases = owner->releases;
    const unsigned destination_releases = other->releases;
    for (size_t i = 0; i < len; i++)
        source.bytes[i] = pattern(i, salt);
    memset(destination.bytes, 0xff, len);
    const uint64_t expected = digest(source.bytes, len);
    check(rust_borrow_digest(source.bytes, len) == expected, "Rust borrow changed data");

    check(release_as(&source, other) == WRONG_OWNER, "foreign release admitted");
    check(owner->releases == source_releases && other->releases == destination_releases,
          "rejection called an allocator");
    check(copy_into(&source, destination.bytes, len - 1) == SHORT, "short transfer admitted");
    for (size_t i = 0; i < len; i++)
        check(destination.bytes[i] == 0xff, "failed transfer changed destination");
    check(copy_into(&source, destination.bytes, len) == OK, "exact copy failed");
    memset(source.bytes, 0, len);
    check(release_as(&source, owner) == OK, "original owner could not release");
    check(release_as(&source, owner) == CLOSED, "second release admitted");
    check(copy_into(&source, destination.bytes, len) == CLOSED, "closed source could be read");
    for (size_t i = 0; i < len; i++)
        check(destination.bytes[i] == pattern(i, salt), "caller-owned copy changed");
    check(rust_borrow_digest(destination.bytes, len) == expected, "copy digest changed");
    check(release_as(&destination, other) == OK, "copy owner could not release");
    check(owner->releases == source_releases + 1 &&
          other->releases == destination_releases + 1, "wrong release count");

    printf("%s,%s,%zu,%u,%016" PRIx64 "\n", owner->name, other->name, len, salt, expected);
}

int main(int argc, char **argv) {
    check(argc == 2, "expected mimalloc path");
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (library == NULL) {
        fprintf(stderr, "%s\n", dlerror());
        return 1;
    }
    mi_malloc = (void *(*)(size_t))dlsym(library, "mi_malloc");
    mi_free = (void (*)(void *))dlsym(library, "mi_free");
    check(mi_malloc && mi_free, "missing named mimalloc interface");
    Dl_info rust, mi_alloc_info, mi_free_info;
    check(dladdr(rust_system_malloc_address(), &rust) != 0 &&
          strstr(rust.dli_fname, "libc.so.6") != NULL, "unexpected Rust System provider");
    check(dladdr((const void *)mi_malloc, &mi_alloc_info) != 0 &&
          dladdr((const void *)mi_free, &mi_free_info) != 0 &&
          mi_alloc_info.dli_fbase == mi_free_info.dli_fbase &&
          strstr(mi_alloc_info.dli_fname, "libmimalloc.so") != NULL &&
          mi_alloc_info.dli_fbase != rust.dli_fbase, "unexpected named provider");
    struct owner system = {"rust-system-glibc", rust_buffer_allocate, rust_buffer_release, 0};
    struct owner named = {"c-mimalloc-named", mi_allocate, mi_release, 0};
    const size_t sizes[] = {1, 2, 15, 16, 17, 1023, 4096, 65536};
    puts("source,destination,bytes,salt,digest");
    for (size_t i = 0; i < sizeof sizes / sizeof *sizes; i++) {
        for (unsigned salt = 0; salt < 4; salt++) {
            trial(&system, &named, sizes[i], salt);
            trial(&named, &system, sizes[i], salt);
        }
    }
    check(system.releases == 64 && named.releases == 64, "missing release");
    check(dlclose(library) == 0, "provider unload failed");
    return 0;
}
