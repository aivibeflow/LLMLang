#include <errno.h>
#include <stdio.h>
#include <sys/reboot.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>

int main(void)
{
    struct utsname release;
    int status = 1;
    if (uname(&release) < 0) {
        perror("uname");
    } else {
        printf("\nLLMLANG_GUEST_KERNEL %s\n", release.release);
        fflush(stdout);
        pid_t child = fork();
        if (child == 0) {
            execl("/probe", "probe", "--llmlang-disposable-guest-probe", (char *)NULL);
            perror("exec probe");
            _exit(127);
        }
        if (child < 0) {
            perror("fork");
        } else {
            int child_status;
            pid_t waited;
            do {
                waited = waitpid(child, &child_status, 0);
            } while (waited < 0 && errno == EINTR);
            if (waited < 0)
                perror("waitpid");
            else if (WIFEXITED(child_status))
                status = WEXITSTATUS(child_status);
            else if (WIFSIGNALED(child_status))
                status = 128 + WTERMSIG(child_status);
        }
    }
    printf("LLMLANG_GUEST_RESULT %d\n", status);
    fflush(stdout);
    if (reboot(RB_POWER_OFF) < 0)
        perror("power off");
    return 1;
}
