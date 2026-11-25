#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <fcntl.h>
#include <pthread.h>
#include <spawn.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

struct setup {
    pthread_barrier_t begin;
    pthread_barrier_t finish;
    const char *scenario;
};

static void wait_at(pthread_barrier_t *barrier)
{
    int error = pthread_barrier_wait(barrier);
    assert(error == 0 || error == PTHREAD_BARRIER_SERIAL_THREAD);
}

static void create(const char *name, mode_t requested)
{
    int fd = open(name, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, requested);
    assert(fd >= 0 && close(fd) == 0);
}

static unsigned mode(const char *name)
{
    struct stat result;
    assert(stat(name, &result) == 0);
    return (unsigned)(result.st_mode & 0777);
}

static void *select_private_mode(void *opaque)
{
    struct setup *control = opaque;
    int overlap = strcmp(control->scenario, "ambient-overlap") == 0;
    int restored = strcmp(control->scenario, "ambient-restored") == 0;
    int local = strcmp(control->scenario, "per-call") == 0;
    mode_t original = 0;
    if (overlap || restored)
        original = umask(0077);
    create("worker", local ? 0600 : 0666);
    if (restored)
        assert(umask(original) == 0077);
    wait_at(&control->begin);
    wait_at(&control->finish);
    if (overlap)
        assert(umask(original) == 0077);
    return NULL;
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    if (strcmp(argv[1], "child") == 0) {
        create("spawned", 0666);
        return 0;
    }
    mode_t inherited = umask(0022);
    struct setup control = {.scenario = argv[1]};
    assert(pthread_barrier_init(&control.begin, NULL, 2) == 0);
    assert(pthread_barrier_init(&control.finish, NULL, 2) == 0);
    pthread_t worker;
    assert(pthread_create(&worker, NULL, select_private_mode, &control) == 0);
    wait_at(&control.begin);
    create("peer", 0666);
    pid_t pid;
    char *arguments[] = {argv[0], "child", NULL};
    assert(posix_spawn(&pid, argv[0], NULL, NULL, arguments, environ) == 0);
    int status;
    assert(waitpid(pid, &status, 0) == pid && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    wait_at(&control.finish);
    assert(pthread_join(worker, NULL) == 0);
    assert(umask(inherited) == 0022);
    assert(pthread_barrier_destroy(&control.begin) == 0);
    assert(pthread_barrier_destroy(&control.finish) == 0);
    printf("worker=%03o\npeer=%03o\nspawned=%03o\n", mode("worker"), mode("peer"), mode("spawned"));
    return 0;
}
