#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int fail(const char *message)
{
    fprintf(stderr, "%s\n", message);
    return 1;
}

static int echo_args(int argc, char **argv)
{
    for (int i = 0; i < argc; ++i) {
        if (i > 0 && putchar(' ') == EOF)
            return 1;
        if (fputs(argv[i], stdout) == EOF)
            return 1;
    }
    return putchar('\n') == EOF || fflush(stdout) == EOF;
}

static int parse_i64(const char *token, int64_t *value)
{
    const char *digits = token;
    if (*digits == '+' || *digits == '-')
        ++digits;
    if (*digits == '\0')
        return 0;
    for (; *digits; ++digits) {
        if (*digits < '0' || *digits > '9')
            return 0;
    }

    errno = 0;
    intmax_t parsed = strtoimax(token, NULL, 10);
    if (errno == ERANGE || parsed < INT64_MIN || parsed > INT64_MAX)
        return 0;
    *value = (int64_t)parsed;
    return 1;
}

static int calculate(void)
{
    char *record = NULL;
    size_t capacity = 0;
    ssize_t length = getline(&record, &capacity, stdin);
    if (length < 0 || memchr(record, '\0', (size_t)length) != NULL) {
        free(record);
        return fail("invalid input");
    }

    const char *delimiters = " \t\r\n";
    char *position;
    char *lhs = strtok_r(record, delimiters, &position);
    char *operation = strtok_r(NULL, delimiters, &position);
    char *rhs = strtok_r(NULL, delimiters, &position);
    char *extra = strtok_r(NULL, delimiters, &position);
    int64_t left, right;
    if (!lhs || !operation || !rhs || extra || operation[1] != '\0' ||
        !parse_i64(lhs, &left) || !parse_i64(rhs, &right)) {
        free(record);
        return fail("invalid input");
    }
    char op = operation[0];
    free(record);

    int64_t result;
    int overflow = 0;
    switch (op) {
    case '+':
        overflow = __builtin_add_overflow(left, right, &result);
        break;
    case '-':
        overflow = __builtin_sub_overflow(left, right, &result);
        break;
    case '*':
        overflow = __builtin_mul_overflow(left, right, &result);
        break;
    case '/':
        if (right == 0)
            return fail("division by zero");
        if (left == INT64_MIN && right == -1)
            return fail("arithmetic overflow");
        result = left / right;
        break;
    default:
        return fail("invalid input");
    }
    if (overflow)
        return fail("arithmetic overflow");
    return printf("%" PRId64 "\n", result) < 0 || fflush(stdout) == EOF;
}

int main(int argc, char **argv)
{
    if (argc < 2)
        return 2;
    if (signal(SIGPIPE, SIG_IGN) == SIG_ERR)
        return 2;
    if (strcmp(argv[1], "hello") == 0)
        return fputs("Hello, world!\n", stdout) == EOF || fflush(stdout) == EOF;
    if (strcmp(argv[1], "echo") == 0)
        return echo_args(argc - 2, argv + 2);
    if (strcmp(argv[1], "calculator") == 0)
        return calculate();
    return 2;
}
