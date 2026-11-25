#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

static pid_t active_child;

static void check(int condition, const char *label) {
    if (!condition) {
        fprintf(stderr, "failed: %s\n", label);
        exit(1);
    }
}

static void cleanup(void) {
    if (active_child > 0) {
        kill(active_child, SIGKILL);
        while (waitpid(active_child, NULL, 0) < 0 && errno == EINTR) {
        }
    }
}

static const char *signal_name(int number) {
    if (number == SIGTERM)
        return "TERM";
    if (number == SIGSTOP)
        return "STOP";
    if (number == SIGCONT)
        return "CONT";
    check(0, "unexpected signal");
    return "";
}

static void report(const char *scenario, const char *step, const char *kind,
                   int data, int is_signal) {
    printf("%s,%s,%s,", scenario, step, kind);
    if (is_signal)
        puts(signal_name(data));
    else
        printf("%d\n", data);
}

static void observe(const char *scenario, const char *step, int flags) {
    siginfo_t info = {0};
    check(waitid(P_PID, (id_t)active_child, &info, flags) == 0, step);
    if (info.si_pid == 0) {
        check(flags & WNOHANG, "unexpected empty blocking waitid");
        report(scenario, step, "none", 0, 0);
        return;
    }
    check(info.si_pid == active_child && info.si_signo == SIGCHLD, "wrong observer identity");
    switch (info.si_code) {
    case CLD_EXITED:
        report(scenario, step, "exit", info.si_status, 0);
        break;
    case CLD_KILLED:
        report(scenario, step, "signal", info.si_status, 1);
        break;
    case CLD_STOPPED:
        report(scenario, step, "stopped", info.si_status, 1);
        break;
    case CLD_CONTINUED:
        report(scenario, step, "continued", info.si_status, 1);
        break;
    default:
        check(0, "unexpected waitid kind");
    }
}

static void consume(const char *scenario, const char *step, int flags) {
    int status = -1;
    pid_t result = waitpid(active_child, &status, flags);
    if (result == 0) {
        check(flags & WNOHANG, "unexpected empty blocking waitpid");
        report(scenario, step, "none", 0, 0);
        return;
    }
    check(result == active_child, step);
    if (WIFEXITED(status))
        report(scenario, step, "exit", WEXITSTATUS(status), 0);
    else if (WIFSIGNALED(status))
        report(scenario, step, "signal", WTERMSIG(status), 1);
    else if (WIFSTOPPED(status))
        report(scenario, step, "stopped", WSTOPSIG(status), 1);
    else if (WIFCONTINUED(status))
        report(scenario, step, "continued", SIGCONT, 1);
    else
        check(0, "unexpected waitpid kind");
}

enum mode { EXIT_143, TERMINATED, STOP_CONTINUE };

static void child(int gate, enum mode mode) {
    char token;
    if (read(gate, &token, 1) != 1)
        _exit(251);
    if (mode == EXIT_143)
        _exit(143);
    if (mode == TERMINATED) {
        raise(SIGTERM);
        _exit(252);
    }
    if (raise(SIGSTOP) != 0 || read(gate, &token, 1) != 1)
        _exit(253);
    _exit(7);
}

static void run(const char *scenario, enum mode mode) {
    int gate[2];
    check(pipe(gate) == 0, "pipe");
    active_child = fork();
    check(active_child >= 0, "fork");
    if (active_child == 0) {
        close(gate[1]);
        child(gate[0], mode);
    }
    close(gate[0]);
    observe(scenario, "empty_waitid", WEXITED | WNOHANG);
    consume(scenario, "empty_waitpid", WNOHANG);
    check(write(gate[1], "a", 1) == 1, "release child");
    if (mode == STOP_CONTINUE) {
        observe(scenario, "peek_stop_a", WSTOPPED | WNOWAIT);
        observe(scenario, "peek_stop_b", WSTOPPED | WNOWAIT);
        consume(scenario, "consume_stop", WUNTRACED);
        observe(scenario, "drained_stop", WSTOPPED | WNOHANG);
        check(kill(active_child, SIGCONT) == 0, "resume child");
        observe(scenario, "peek_continue_a", WCONTINUED | WNOWAIT);
        observe(scenario, "peek_continue_b", WCONTINUED | WNOWAIT);
        consume(scenario, "consume_continue", WCONTINUED);
        observe(scenario, "drained_continue", WCONTINUED | WNOHANG);
        check(write(gate[1], "b", 1) == 1, "allow exit");
    }
    close(gate[1]);
    observe(scenario, "peek_exit_a", WEXITED | WNOWAIT);
    observe(scenario, "peek_exit_b", WEXITED | WNOWAIT);
    consume(scenario, "reap", 0);
    int status;
    const pid_t reaped = active_child;
    active_child = 0;
    errno = 0;
    check(waitpid(reaped, &status, WNOHANG) == -1 && errno == ECHILD, "already reaped");
    report(scenario, "after_reap", "no_child", 0, 0);
}

int main(void) {
    struct sigaction action = {.sa_handler = SIG_DFL};
    sigemptyset(&action.sa_mask);
    check(sigaction(SIGCHLD, &action, NULL) == 0, "default SIGCHLD");
    check(sigaction(SIGTERM, &action, NULL) == 0, "default SIGTERM");
    check(sigaction(SIGCONT, &action, NULL) == 0, "default SIGCONT");
    check(sigprocmask(SIG_SETMASK, &action.sa_mask, NULL) == 0, "unblock fixture signals");
    check(atexit(cleanup) == 0, "cleanup registration");
    puts("scenario,step,kind,detail");
    run("exit-143", EXIT_143);
    run("signal-term", TERMINATED);
    run("stop-continue-exit", STOP_CONTINUE);
    return 0;
}
