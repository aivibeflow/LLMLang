#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

enum { PAGES = 64 };

struct event {
    const char *name;
    unsigned int type;
    uint64_t config;
    int fd;
    int error_value;
};

struct counters {
    uint64_t value;
    uint64_t enabled;
    uint64_t running;
};

static void die(const char *operation)
{
    perror(operation);
    exit(EXIT_FAILURE);
}

static void open_for_this_thread(struct event *e)
{
    struct perf_event_attr attr = {
        .type = e->type,
        .size = sizeof(attr),
        .config = e->config,
        .read_format = PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING,
        .disabled = 1,
        .exclude_kernel = 1,
        .exclude_hv = 1,
    };
    e->fd = (int)syscall(SYS_perf_event_open, &attr, 0, -1, -1, PERF_FLAG_FD_CLOEXEC);
    if (e->fd < 0)
        e->error_value = errno;
}

static void emit_event(const struct event *e)
{
    if (e->fd < 0) {
        printf("%s,%d,0,0,0\n", e->name, e->error_value);
        return;
    }
    struct counters observed;
    if (ioctl(e->fd, PERF_EVENT_IOC_DISABLE, 0) != 0)
        die("disable counter");
    if (read(e->fd, &observed, sizeof(observed)) != sizeof(observed))
        die("read counter");
    close(e->fd);
    printf("%s,0,%" PRIu64 ",%" PRIu64 ",%" PRIu64 "\n",
           e->name, observed.value, observed.enabled, observed.running);
}

static uint64_t clock_ns(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t) != 0)
        die("clock_gettime");
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}

int main(void)
{
    struct event definitions[] = {
        {"task_clock", PERF_TYPE_SOFTWARE, PERF_COUNT_SW_TASK_CLOCK, -1, 0},
        {"context_switches", PERF_TYPE_SOFTWARE, PERF_COUNT_SW_CONTEXT_SWITCHES, -1, 0},
        {"minor_faults", PERF_TYPE_SOFTWARE, PERF_COUNT_SW_PAGE_FAULTS_MIN, -1, 0},
        {"cycles", PERF_TYPE_HARDWARE, PERF_COUNT_HW_CPU_CYCLES, -1, 0},
        {"instructions", PERF_TYPE_HARDWARE, PERF_COUNT_HW_INSTRUCTIONS, -1, 0},
    };
    size_t count = sizeof(definitions) / sizeof(definitions[0]);
    for (size_t index = 0; index < count; ++index)
        open_for_this_thread(&definitions[index]);

    long page = sysconf(_SC_PAGESIZE);
    if (page < 1)
        die("page size");
    size_t length = (size_t)page * PAGES;
    volatile unsigned char *memory = mmap(NULL, length, PROT_READ | PROT_WRITE,
                                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (memory == MAP_FAILED)
        die("mmap");
    if (madvise((void *)memory, length, MADV_NOHUGEPAGE) != 0)
        die("madvise");

    struct rusage before;
    struct rusage after;
    if (getrusage(RUSAGE_THREAD, &before) != 0)
        die("getrusage");
    uint64_t start = clock_ns();
    for (size_t index = 0; index < count; ++index)
        if (definitions[index].fd >= 0 && ioctl(definitions[index].fd, PERF_EVENT_IOC_ENABLE, 0) != 0)
            die("enable counter");
    for (size_t offset = 0; offset < length; offset += (size_t)page)
        memory[offset] = 17;
    while (clock_ns() - start < UINT64_C(20000000))
        ;
    uint64_t elapsed = clock_ns() - start;
    if (getrusage(RUSAGE_THREAD, &after) != 0)
        die("getrusage");
    for (size_t index = 0; index < count; ++index)
        emit_event(&definitions[index]);

    printf("fallback,%" PRIu64 ",%ld,%ld,%ld\n", elapsed, after.ru_minflt - before.ru_minflt,
           after.ru_nvcsw - before.ru_nvcsw, after.ru_nivcsw - before.ru_nivcsw);
    if (munmap((void *)memory, length) != 0)
        die("munmap");
}
