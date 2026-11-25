#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

struct attempt {
    int requested;
    int accepted;
};

struct sink {
    int fd;
    int budget;
    int limit;
    int interrupt;
    struct attempt calls[16];
    int count;
};

static int try_write(struct sink *sink, const unsigned char *data, int size) {
    int result;
    if (sink->interrupt) {
        sink->interrupt = 0;
        result = -EINTR;
    } else if (sink->budget == 0) {
        result = -EIO;
    } else {
        result = size < sink->limit ? size : sink->limit;
        if (result > sink->budget) {
            result = sink->budget;
        }
        if (write(sink->fd, data, (size_t)result) != result) {
            exit(2);
        }
        sink->budget -= result;
    }
    sink->calls[sink->count++] = (struct attempt){size, result};
    return result;
}

static int emit_chunk(struct sink *sink, const unsigned char *data, int size, int drop_short) {
    int offset = 0;
    while (offset < size) {
        int accepted = try_write(sink, data + offset, size - offset);
        if (accepted == -EINTR) {
            continue;
        }
        if (accepted < 0) {
            return -accepted;
        }
        if (drop_short) {
            break;
        }
        offset += accepted;
    }
    return 0;
}

int main(void) {
    const unsigned char message[] = {0x41, 0x00, 0xff, 0x4a, 0x20};
    int length, boundaries, budget, limit, interrupt, drop_short;
    while (scanf("%d %d %d %d %d %d", &length, &boundaries, &budget, &limit,
                 &interrupt, &drop_short) == 6) {
        int fd[2];
        if (pipe(fd) != 0) {
            return 3;
        }
        struct sink sink = {.fd = fd[1], .budget = budget, .limit = limit, .interrupt = interrupt};
        int start = 0;
        int status = 0;
        for (int end = 1; end <= length; end++) {
            if (end == length || (boundaries & (1 << (end - 1)))) {
                status = emit_chunk(&sink, message + start, end - start, drop_short);
                if (status) {
                    break;
                }
                start = end;
            }
        }
        if (close(fd[1]) != 0) {
            return 4;
        }
        printf("%s ", status == EIO ? "eio" : "ok");
        int total = 0;
        ssize_t count;
        unsigned char buffer[sizeof(message)];
        while ((count = read(fd[0], buffer, sizeof(buffer))) > 0) {
            for (ssize_t i = 0; i < count; i++) {
                printf("%02x", (unsigned int)buffer[i]);
            }
            total += (int)count;
        }
        if (count < 0 || close(fd[0]) != 0) {
            return 5;
        }
        if (total == 0) {
            printf("-");
        }
        for (int i = 0; i < sink.count; i++) {
            int accepted = sink.calls[i].accepted;
            const char *failure = accepted == -EINTR ? "eintr" : "eio";
            if (accepted < 0) {
                printf(" %d:%s", sink.calls[i].requested, failure);
            } else {
                printf(" %d:%d", sink.calls[i].requested, accepted);
            }
        }
        puts("");
    }
    return ferror(stdout) ? 6 : 0;
}
