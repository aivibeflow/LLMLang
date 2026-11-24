#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <unistd.h>

static void require(bool condition, const char *stage)
{
    if (!condition) {
        fprintf(stderr, "%s failed (errno=%d)\n", stage, errno);
        exit(EXIT_FAILURE);
    }
}

static bool flag(const char *value)
{
    require(strcmp(value, "0") == 0 || strcmp(value, "1") == 0, "parse flag");
    return strcmp(value, "1") == 0;
}

static bool descriptor_open(int fd)
{
    int result = fcntl(fd, F_GETFD);
    require(result >= 0 || errno == EBADF, "inspect descriptor");
    return result >= 0;
}

static bool try_lock(int contender)
{
    int result = flock(contender, LOCK_EX | LOCK_NB);
    require(result == 0 || errno == EWOULDBLOCK, "try competing lock");
    return result == 0;
}

int main(int argc, char *argv[])
{
    require(argc == 7, "parse arguments");
    bool early = flag(argv[1]);
    bool wants_value = flag(argv[2]);
    bool break_pipe = flag(argv[3]);
    bool hold_duplicate = flag(argv[4]);

    struct sigaction ignore = {.sa_handler = SIG_IGN};
    require(sigemptyset(&ignore.sa_mask) == 0, "initialize signal mask");
    require(sigaction(SIGPIPE, &ignore, NULL) == 0, "ignore SIGPIPE");

    int owner = open(argv[5], O_RDWR | O_CLOEXEC);
    require(owner >= 0 && try_lock(owner), "acquire original lock");
    int contender = open(argv[6], O_RDWR | O_CLOEXEC);
    require(contender >= 0, "open independent contender");
    int duplicate = -1;
    if (hold_duplicate) {
        duplicate = dup(owner);
        require(duplicate >= 0, "duplicate foreign descriptor");
    }

    int ends[2];
    require(pipe(ends) == 0, "create cleanup pipe");
    if (break_pipe)
        require(close(ends[0]) == 0, "remove pipe reader");

    FILE *stream = fdopen(ends[1], "w");
    require(stream != NULL, "associate stdio stream");
    char stream_buffer[64];
    require(setvbuf(stream, stream_buffer, _IOFBF, sizeof stream_buffer) == 0, "buffer stream");
    require(fputc('x', stream) == 'x', "buffer pending byte");
    if (!break_pipe) {
        struct pollfd readable = {.fd = ends[0], .events = POLLIN};
        require(poll(&readable, 1, 0) == 0, "verify byte is still buffered");
    }

    bool forwarded = early && wants_value;
    if (forwarded)
        puts("transfer");
    int close_result = fclose(stream);
    int close_errno = close_result == 0 ? 0 : errno;
    require(close_errno == (break_pipe ? EPIPE : 0), "observe expected flush/close result");
    puts(close_result == 0 ? "fclose_ok" : "fclose_epipe");
    require(!descriptor_open(ends[1]), "observe closed stdio descriptor");
    puts("stream_fd_closed");
    if (!break_pipe) {
        char byte;
        require(read(ends[0], &byte, 1) == 1 && byte == 'x', "read flushed byte");
        require(read(ends[0], &byte, 1) == 0, "observe pipe EOF");
        require(close(ends[0]) == 0, "close pipe reader");
        puts("flushed_byte");
    }

    if (!early && wants_value && close_result == 0) {
        forwarded = true;
        puts("transfer");
    }
    if (!forwarded) {
        require(close(owner) == 0, "release unforwarded owner");
        puts("provider_close");
    }
    require(descriptor_open(owner) == forwarded, "inspect original descriptor");
    puts(forwarded ? "owner_fd_open" : "owner_fd_closed");
    if (hold_duplicate) {
        require(descriptor_open(duplicate), "inspect surviving duplicate");
        puts("duplicate_fd_open");
    }

    bool started = try_lock(contender);
    puts(started ? "second_started" : "second_refused");
    if (forwarded) {
        require(close(owner) == 0, "caller releases forwarded owner");
        puts("caller_close");
    }
    if (hold_duplicate) {
        require(close(duplicate) == 0, "foreign alias releases duplicate");
        puts("duplicate_close");
    }
    if (!started) {
        require(try_lock(contender), "admit after final owner release");
        puts("second_retry_started");
    }

    require(close(contender) == 0, "release competing lock");
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
