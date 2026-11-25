#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>

static int receive_fd(int socket_fd, char *tag)
{
    union {
        struct cmsghdr alignment;
        unsigned char bytes[CMSG_SPACE(sizeof(int))];
    } control = {0};
    struct iovec payload = {.iov_base = tag, .iov_len = 1};
    struct msghdr message = {
        .msg_iov = &payload,
        .msg_iovlen = 1,
        .msg_control = control.bytes,
        .msg_controllen = sizeof(control.bytes),
    };
    if (recvmsg(socket_fd, &message, MSG_CMSG_CLOEXEC) != 1 ||
        (message.msg_flags & (MSG_CTRUNC | MSG_TRUNC))) {
        return -1;
    }
    struct cmsghdr *header = CMSG_FIRSTHDR(&message);
    if (header == NULL || header->cmsg_len != CMSG_LEN(sizeof(int)) ||
        header->cmsg_level != SOL_SOCKET || header->cmsg_type != SCM_RIGHTS ||
        CMSG_NXTHDR(&message, header) != NULL) {
        return -1;
    }
    int result;
    memcpy(&result, CMSG_DATA(header), sizeof(result));
    return result;
}

int main(int argc, char **argv)
{
    if (argc != 2 || setvbuf(stdout, NULL, _IOLBF, 0) != 0) {
        return 1;
    }
    char *end;
    errno = 0;
    long socket_fd = strtol(argv[1], &end, 10);
    if (errno != 0 || *end != '\0' || socket_fd < 0 || socket_fd > INT32_MAX) {
        return 1;
    }

    int owned[2] = {-1, -1};
    char command[16];
    puts("ready");
    while (fgets(command, sizeof(command), stdin) != NULL) {
        if (strcmp(command, "receive\n") == 0) {
            char tag;
            int fd = receive_fd((int) socket_fd, &tag);
            if (fd < 0 || (tag != '0' && tag != '1') || owned[tag - '0'] >= 0) {
                return 2;
            }
            struct stat metadata;
            if (fstat(fd, &metadata) != 0 || fcntl(fd, F_GETFD) != FD_CLOEXEC) {
                return 3;
            }
            owned[tag - '0'] = fd;
            printf("received %c %ju %ju\n", tag,
                   (uintmax_t) metadata.st_dev, (uintmax_t) metadata.st_ino);
        } else if (strcmp(command, "close 0\n") == 0 || strcmp(command, "close 1\n") == 0) {
            char tag = command[6];
            int index = tag - '0';
            if (owned[index] < 0 || close(owned[index]) != 0) {
                return 4;
            }
            owned[index] = -1;
            printf("closed %c\n", tag);
        } else if (strcmp(command, "exit\n") == 0) {
            return 0;
        } else {
            return 5;
        }
    }
    return 6;
}
