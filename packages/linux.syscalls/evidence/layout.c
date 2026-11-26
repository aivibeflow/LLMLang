/* Compare selected native C ABI layouts with the Rust adapter layout checks. */
#define _GNU_SOURCE
#include <assert.h>
#include <linux/aio_abi.h>
#include <linux/bpf.h>
#include <linux/capability.h>
#include <linux/fanotify.h>
#include <linux/futex.h>
#include <linux/sched.h>
#include <linux/mount.h>
#include <linux/io_uring.h>
#include <linux/openat2.h>
#include <linux/perf_event.h>
#include <linux/stat.h>
#include <netinet/in.h>
#include <poll.h>
#include <stddef.h>
#include <stdint.h>
#include <signal.h>
#include <sys/epoll.h>
#include <sys/inotify.h>
#include <sys/resource.h>
#include <sys/sem.h>
#include <sys/select.h>
#include <sys/shm.h>
#include <sys/socket.h>
#include <sys/signalfd.h>
#include <sys/stat.h>
#include <sys/sysinfo.h>
#include <sys/time.h>
#include <sys/timex.h>
#include <sys/times.h>
#include <sys/vfs.h>
#include <sys/uio.h>
#include <sys/utsname.h>
#include <time.h>

#define ALIGN(type, expected) _Static_assert(_Alignof(type) == expected, #type)
#define SIZE(type, expected) _Static_assert(sizeof(type) == expected, #type)
#define OFFSET(type, field, expected) \
    _Static_assert(offsetof(type, field) == expected, #type "." #field)

SIZE(struct stat, 144);
OFFSET(struct stat, st_mode, 24);
OFFSET(struct stat, st_rdev, 40);
OFFSET(struct stat, st_size, 48);
OFFSET(struct stat, st_atim, 72);
OFFSET(struct stat, st_ctim, 104);

SIZE(struct statfs, 120);
ALIGN(struct statfs, 8);
OFFSET(struct statfs, f_fsid, 56);
OFFSET(struct statfs, f_namelen, 64);

SIZE(struct statx, 256);
ALIGN(struct statx, 8);
OFFSET(struct statx, stx_size, 40);
OFFSET(struct statx, stx_atime, 64);
OFFSET(struct statx, stx_mtime, 112);

SIZE(struct sembuf, 6);
OFFSET(struct sembuf, sem_op, 2);
OFFSET(struct sembuf, sem_flg, 4);
SIZE(struct shmid_ds, 112);
OFFSET(struct shmid_ds, shm_segsz, 48);
OFFSET(struct shmid_ds, shm_nattch, 88);

SIZE(struct msghdr, 56);
OFFSET(struct msghdr, msg_flags, 48);
SIZE(struct io_event, 32);
OFFSET(struct io_event, obj, 8);
OFFSET(struct io_event, res, 16);
SIZE(struct iocb, 64);
OFFSET(struct iocb, aio_lio_opcode, 16);
OFFSET(struct iocb, aio_flags, 56);
_Static_assert(IOCB_CMD_FSYNC == 2, "IOCB_CMD_FSYNC");
SIZE(struct mmsghdr, 64);
OFFSET(struct mmsghdr, msg_len, 56);

SIZE(struct open_how, 24);
OFFSET(struct open_how, mode, 8);
OFFSET(struct open_how, resolve, 16);
_Static_assert(RESOLVE_BENEATH == 8 && RESOLVE_NO_MAGICLINKS == 2, "openat2 scope");

SIZE(fd_set, 128);
_Static_assert(FD_SETSIZE == 1024, "fd_set capacity");
SIZE(siginfo_t, 128);
ALIGN(siginfo_t, 8);
OFFSET(siginfo_t, si_signo, 0);
OFFSET(siginfo_t, si_errno, 4);
OFFSET(siginfo_t, si_code, 8);
OFFSET(siginfo_t, si_pid, 16);
OFFSET(siginfo_t, si_uid, 20);
OFFSET(siginfo_t, si_value, 24);
_Static_assert(SI_USER == 0 && SI_QUEUE == -1 && SI_TKILL == -6, "wait signal codes");
OFFSET(siginfo_t, si_status, 24);

SIZE(struct mount_attr, 32);
OFFSET(struct mount_attr, attr_clr, 8);
OFFSET(struct mount_attr, propagation, 16);
OFFSET(struct mount_attr, userns_fd, 24);
SIZE(struct fanotify_event_metadata, 24);
OFFSET(struct fanotify_event_metadata, mask, 8);
OFFSET(struct fanotify_event_metadata, fd, 16);
OFFSET(struct fanotify_event_metadata, pid, 20);
_Static_assert(CLONE_ARGS_SIZE_VER0 == 64, "clone3 v0 request prefix");
OFFSET(struct clone_args, exit_signal, 32);
OFFSET(struct clone_args, tls, 56);
SIZE(struct robust_list_head, 24);
OFFSET(struct robust_list_head, futex_offset, 8);
OFFSET(struct robust_list_head, list_op_pending, 16);
SIZE(struct futex_waitv, 24);
OFFSET(struct futex_waitv, uaddr, 8);
OFFSET(struct futex_waitv, flags, 16);
SIZE(struct timex, 208);
ALIGN(struct timex, 8);
OFFSET(struct timex, time, 72);

SIZE(struct inotify_event, 16);
OFFSET(struct inotify_event, mask, 4);
OFFSET(struct inotify_event, cookie, 8);
OFFSET(struct inotify_event, len, 12);
OFFSET(struct inotify_event, name, 16);

SIZE(struct iovec, 16);
OFFSET(struct iovec, iov_len, 8);
SIZE(struct pollfd, 8);
OFFSET(struct pollfd, revents, 6);
SIZE(struct epoll_event, 12);
ALIGN(struct epoll_event, 1);
OFFSET(struct epoll_event, data, 4);
SIZE(struct sockaddr_in, 16);
ALIGN(struct sockaddr_in, 4);
OFFSET(struct sockaddr_in, sin_port, 2);
OFFSET(struct sockaddr_in, sin_addr, 4);

SIZE(struct timespec, 16);
OFFSET(struct timespec, tv_nsec, 8);
SIZE(struct timeval, 16);
OFFSET(struct timeval, tv_usec, 8);
SIZE(struct sigevent, 64);
ALIGN(struct sigevent, 8);
OFFSET(struct sigevent, sigev_signo, 8);
OFFSET(struct sigevent, sigev_notify, 12);
_Static_assert(SIGEV_NONE == 1, "SIGEV_NONE");
SIZE(struct itimerval, 32);
OFFSET(struct itimerval, it_value, 16);
SIZE(struct tms, 32);
OFFSET(struct tms, tms_cstime, 24);
SIZE(struct itimerspec, 32);
OFFSET(struct itimerspec, it_value, 16);
SIZE(struct rusage, 144);
OFFSET(struct rusage, ru_stime, 16);
OFFSET(struct rusage, ru_maxrss, 32);

SIZE(struct sysinfo, 112);
OFFSET(struct sysinfo, procs, 80);
OFFSET(struct sysinfo, totalhigh, 88);
OFFSET(struct sysinfo, mem_unit, 104);
SIZE(struct utsname, 390);
SIZE(struct __user_cap_header_struct, 8);
SIZE(struct __user_cap_data_struct, 12);
SIZE(struct signalfd_siginfo, 128);
OFFSET(struct signalfd_siginfo, ssi_pid, 12);
OFFSET(struct signalfd_siginfo, ssi_uid, 16);

OFFSET(union bpf_attr, key, 8);
OFFSET(union bpf_attr, value, 16);
OFFSET(union bpf_attr, flags, 24);
_Static_assert(PERF_ATTR_SIZE_VER0 == 64, "perf_event_attr base size");
_Static_assert(PERF_ATTR_SIZE_VER1 == 72, "perf_event_attr probe size");
OFFSET(struct perf_event_attr, uprobe_path, 56);
OFFSET(struct perf_event_attr, probe_offset, 64);
SIZE(struct io_uring_sqe, 64);
OFFSET(struct io_uring_sqe, len, 24);
OFFSET(struct io_uring_sqe, user_data, 32);
SIZE(struct io_uring_cqe, 16);
OFFSET(struct io_uring_cqe, res, 8);
SIZE(struct io_uring_params, 120);
OFFSET(struct io_uring_params, sq_off, 40);
OFFSET(struct io_uring_params, cq_off, 80);
SIZE(struct io_uring_probe, 16);
SIZE(struct io_uring_probe_op, 8);

int main(void) {
    struct perf_event_attr attr = {0};
    attr.exclude_kernel = 1;
    attr.exclude_hv = 1;
    const unsigned char *representation = (const unsigned char *)&attr;
    assert(representation[40] == 0x60);
    return 0;
}
