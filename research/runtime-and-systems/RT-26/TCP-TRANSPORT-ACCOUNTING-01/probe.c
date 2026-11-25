#define _GNU_SOURCE
#include <arpa/inet.h>
#include <inttypes.h>
#include <linux/tcp.h>
#include <netinet/in.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static void require(int condition, const char *message)
{
    if (condition)
        return;
    perror(message);
    exit(1);
}

struct session {
    int sender;
    int reader;
    int alias;
    struct tcp_info sender_baseline;
    struct tcp_info reader_baseline;
    int enqueued;
    int consumed;
    int copied[2];
    int charged[2];
    unsigned char last_bytes[64];
    int last_count;
};

static struct tcp_info info(int fd)
{
    struct tcp_info data = {0};
    socklen_t length = sizeof(data);
    require(getsockopt(fd, IPPROTO_TCP, TCP_INFO, &data, &length) == 0, "TCP_INFO");
    require(length >= offsetof(struct tcp_info, tcpi_bytes_retrans) + sizeof(data.tcpi_bytes_retrans),
            "TCP_INFO reply too short");
    return data;
}

static uint64_t cookie(int fd)
{
    uint64_t value = 0;
    socklen_t length = sizeof(value);
    require(getsockopt(fd, SOL_SOCKET, SO_COOKIE, &value, &length) == 0, "SO_COOKIE");
    require(length == sizeof(value), "SO_COOKIE size");
    return value;
}

static int queued(int fd)
{
    int bytes = 0;
    require(ioctl(fd, FIONREAD, &bytes) == 0, "FIONREAD");
    return bytes;
}

static struct session setup(void)
{
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    require(listener >= 0, "listener");
    struct sockaddr_in address = {
        .sin_family = AF_INET, .sin_port = 0, .sin_addr.s_addr = htonl(INADDR_LOOPBACK)
    };
    require(bind(listener, (struct sockaddr *)&address, sizeof(address)) == 0, "bind");
    require(listen(listener, 1) == 0, "listen");
    socklen_t size = sizeof(address);
    require(getsockname(listener, (struct sockaddr *)&address, &size) == 0, "getsockname");
    int sender = socket(AF_INET, SOCK_STREAM, 0);
    require(sender >= 0, "sender");
    require(connect(sender, (struct sockaddr *)&address, size) == 0, "connect");
    int reader = accept(listener, NULL, NULL);
    require(reader >= 0 && close(listener) == 0, "accept");
    int alias = dup(reader);
    require(alias >= 0 && cookie(alias) == cookie(reader) && cookie(sender) != cookie(reader),
            "descriptor ownership");
    int enabled = 1;
    require(setsockopt(sender, IPPROTO_TCP, TCP_NODELAY, &enabled, sizeof(enabled)) == 0, "TCP_NODELAY");
    return (struct session){ .sender = sender, .reader = reader, .alias = alias,
                             .sender_baseline = info(sender), .reader_baseline = info(reader) };
}

static unsigned char byte_at(int index)
{
    return (unsigned char)((index * 17 + 13) % 251);
}

static void enqueue(struct session *self, int amount)
{
    unsigned char message[64];
    require(amount > 0 && amount <= (int)sizeof(message), "send length");
    for (int index = 0; index < amount; index++)
        message[index] = byte_at(self->enqueued + index);
    int completed = 0;
    while (completed < amount) {
        ssize_t result = send(self->sender, message + completed, (size_t)(amount - completed), 0);
        require(result > 0, "send");
        completed += (int)result;
    }
    self->enqueued += amount;
    struct timespec pause = { .tv_nsec = 1000000 };
    for (int tries = 0; tries < 3000; tries++) {
        struct tcp_info sent = info(self->sender);
        if (sent.tcpi_bytes_acked - self->sender_baseline.tcpi_bytes_acked >= (uint64_t)self->enqueued
            && queued(self->reader) == self->enqueued - self->consumed)
            return;
        nanosleep(&pause, NULL);
    }
    require(0, "transport frontier deadline");
}

static void receive(struct session *self, int task, int amount, int peek)
{
    unsigned char buffer[64];
    int fd = task == 0 ? self->reader : self->alias;
    int ready = self->enqueued - self->consumed;
    int expected = amount < ready ? amount : ready;
    require(expected > 0 && amount <= (int)sizeof(buffer), "receive length");
    ssize_t result = recv(fd, buffer, (size_t)amount, MSG_DONTWAIT | (peek ? MSG_PEEK : 0));
    require(result == expected, "receive");
    self->last_count = (int)result;
    for (int index = 0; index < result; index++) {
        require(buffer[index] == byte_at(self->consumed + index), "byte observation");
        self->last_bytes[index] = buffer[index];
    }
    self->copied[task] += (int)result;
    if (!peek) {
        self->charged[task] += (int)result;
        self->consumed += (int)result;
    }
}

static void observe(struct session *self, const char *phase)
{
    struct tcp_info sent = info(self->sender);
    struct tcp_info received = info(self->reader);
    struct tcp_info alias = info(self->alias);
    uint64_t pushed = sent.tcpi_bytes_sent - self->sender_baseline.tcpi_bytes_sent;
    uint64_t acknowledged = sent.tcpi_bytes_acked - self->sender_baseline.tcpi_bytes_acked;
    uint64_t arrived = received.tcpi_bytes_received - self->reader_baseline.tcpi_bytes_received;
    uint64_t alias_arrived = alias.tcpi_bytes_received - self->reader_baseline.tcpi_bytes_received;
    uint64_t resent = sent.tcpi_bytes_retrans - self->sender_baseline.tcpi_bytes_retrans;
    printf("%s\t%d\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64
           "\t%d\t%d\t%d\t%d\t%d\t%d\t",
           phase, self->enqueued, pushed, acknowledged, arrived, alias_arrived, resent,
           queued(self->reader), queued(self->alias), self->copied[0], self->copied[1],
           self->charged[0], self->charged[1]);
    if (!self->last_count)
        putchar('-');
    for (int index = 0; index < self->last_count; index++)
        printf("%02x", self->last_bytes[index]);
    putchar('\n');
    self->last_count = 0;
}

int main(int argc, char **argv)
{
    require(argc == 6, "arguments");
    struct session self = setup();
    observe(&self, "initial");
    enqueue(&self, atoi(argv[1]));
    observe(&self, "enqueue-first");
    receive(&self, 1, atoi(argv[3]), 1);
    observe(&self, "peek-second-reader");
    receive(&self, 0, atoi(argv[4]), 0);
    observe(&self, "read-first");
    enqueue(&self, atoi(argv[2]));
    observe(&self, "enqueue-second");
    receive(&self, 1, atoi(argv[5]), 0);
    observe(&self, "read-second");
    receive(&self, 0, atoi(argv[3]), 1);
    observe(&self, "peek-first-reader");
    receive(&self, 0, self.enqueued - self.consumed, 0);
    observe(&self, "drain-first");
    require(close(self.alias) == 0 && close(self.reader) == 0 && close(self.sender) == 0, "close");
    return 0;
}
