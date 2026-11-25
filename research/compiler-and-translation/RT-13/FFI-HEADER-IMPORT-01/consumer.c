#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <sqlite3.h>
#include <openssl/evp.h>

static void require(int condition, const char *message)
{
    if (condition)
        return;
    fprintf(stderr, "%s\n", message);
    exit(1);
}

static void sqlite_case(const char *symbol, int pending, int value)
{
    sqlite3 *database = NULL;
    sqlite3_stmt *statements[2] = {NULL, NULL};
    require(pending >= 0 && pending <= 2, "pending");
    require(sqlite3_open(":memory:", &database) == SQLITE_OK, "open database");
    char statement[32];
    for (int index = 0; index < pending; index++) {
        snprintf(statement, sizeof(statement), "SELECT %d", value + index);
        require(sqlite3_prepare_v2(database, statement, -1, &statements[index], NULL) == SQLITE_OK,
                "prepare statement");
    }
    int deferred = !strcmp(symbol, "sqlite3_close_v2");
    int close_result = deferred ? sqlite3_close_v2(database) : sqlite3_close(database);
    printf("%d", close_result);
    for (int index = 0; index < pending; index++) {
        int step = sqlite3_step(statements[index]);
        printf("\t%d\t%d", step, sqlite3_column_int(statements[index], 0));
        printf("\t%d", sqlite3_finalize(statements[index]));
    }
    if (close_result == SQLITE_BUSY)
        printf("\t%d", sqlite3_close(database));
    else
        printf("\t-1");
    puts("");
}

static void print_digest(const unsigned char *data, unsigned int size)
{
    for (unsigned int index = 0; index < size; index++)
        printf("%02x", data[index]);
}

static void crypto_case(const char *symbol, const char *data)
{
    EVP_MD_CTX *context = EVP_MD_CTX_new();
    require(context != NULL, "digest context");
    require(EVP_DigestInit_ex(context, EVP_sha256(), NULL), "initial digest init");
    require(EVP_DigestUpdate(context, data, strlen(data)), "initial update");
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int size = 0;
    int final_result = !strcmp(symbol, "EVP_DigestFinal")
        ? EVP_DigestFinal(context, digest, &size)
        : EVP_DigestFinal_ex(context, digest, &size);
    printf("%d\t", final_result);
    print_digest(digest, size);
    int retained = EVP_MD_CTX_get0_md(context) != NULL;
    int reinit = EVP_DigestInit_ex(context, NULL, NULL);
    printf("\t%d\t%d\t", retained, reinit);
    if (reinit) {
        require(EVP_DigestUpdate(context, data, strlen(data)), "reinitialized update");
        require(EVP_DigestFinal_ex(context, digest, &size), "reinitialized final");
        print_digest(digest, size);
    } else {
        printf("-");
    }
    puts("");
    EVP_MD_CTX_free(context);
}

static void descriptor_case(const char *symbol, int value)
{
    int descriptors[2];
    require(pipe(descriptors) == 0, "pipe");
    int is_dup = !strcmp(symbol, "dup");
    int result = is_dup ? dup(descriptors[0]) : close(descriptors[0]);
    require(result >= 0, "descriptor operation");
    errno = 0;
    int original_valid = fcntl(descriptors[0], F_GETFD) != -1;
    int error = errno;
    int read_value = -1;
    if (is_dup) {
        unsigned char sent = (unsigned char)value;
        unsigned char received;
        require(close(descriptors[0]) == 0, "retire original");
        require(write(descriptors[1], &sent, 1) == 1, "send");
        require(read(result, &received, 1) == 1, "receive by duplicate");
        read_value = received;
        require(close(result) == 0, "close duplicate");
    }
    require(close(descriptors[1]) == 0, "close writer");
    printf("%d\t%d\t%d\t%d\n", result > 0, original_valid, error, read_value);
}

int main(int argc, char **argv)
{
    require(argc >= 4, "missing selector");
    if (!strcmp(argv[1], "sqlite")) {
        require(argc == 5, "sqlite needs count and value");
        sqlite_case(argv[2], atoi(argv[3]), atoi(argv[4]));
    } else if (!strcmp(argv[1], "crypto")) {
        crypto_case(argv[2], argv[3]);
    } else if (!strcmp(argv[1], "libc")) {
        descriptor_case(argv[2], atoi(argv[3]));
    } else {
        require(0, "unknown selector");
    }
}
