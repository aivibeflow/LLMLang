"""Reviewed user-pointer semantics that Linux C prototypes leave implicit."""

# Required NUL-terminated inputs. The paths are copied by the kernel's path
# lookup (fs/namei.c). The other strings use the subsystem's bounded user copy.
STRINGS = {
    "open": "filename", "openat": "filename", "openat2": "filename",
    "stat": "filename", "lstat": "filename", "access": "filename",
    "execve": "filename", "execveat": "filename",
    "truncate": "path", "chdir": "filename", "rename": "oldname newname",
    "mkdir": "pathname", "rmdir": "pathname", "creat": "pathname",
    "link": "oldname newname", "unlink": "pathname", "symlink": "oldname newname",
    "readlink": "path", "chmod": "filename", "chown": "filename", "lchown": "filename",
    "utime": "filename", "utimes": "filename", "mknod": "filename", "statfs": "pathname",
    "pivot_root": "new_root put_old", "chroot": "filename", "mount": "dir_name",
    "umount2": "name", "swapon": "specialfile", "swapoff": "specialfile",
    "init_module": "uargs", "delete_module": "name_user", "finit_module": "uargs",
    "setxattr": "pathname name", "lsetxattr": "pathname name", "fsetxattr": "name",
    "getxattr": "pathname name", "lgetxattr": "pathname name", "fgetxattr": "name",
    "listxattr": "pathname", "llistxattr": "pathname",
    "removexattr": "pathname name", "lremovexattr": "pathname name", "fremovexattr": "name",
    "mq_open": "u_name", "mq_unlink": "u_name", "add_key": "_type",
    "request_key": "_type _description", "inotify_add_watch": "pathname",
    "mkdirat": "pathname", "mknodat": "filename", "fchownat": "filename",
    "unlinkat": "pathname", "renameat": "oldname newname", "linkat": "oldname newname",
    "symlinkat": "oldname newname", "readlinkat": "pathname",
    "fchmodat": "filename", "faccessat": "filename", "fchmodat2": "filename",
    "name_to_handle_at": "name", "renameat2": "oldname newname", "memfd_create": "uname",
    "open_tree": "filename", "move_mount": "from_pathname to_pathname", "fsopen": "_fs_name",
    "fspick": "path", "faccessat2": "filename", "mount_setattr": "path",
}

# NULL can select an fd, a control operation, or the absence of optional data.
NULLABLE_STRINGS = {
    "acct": "name",
    "mount": "dev_name type",
    "quotactl": "special",
    "add_key": "_description",
    "request_key": "_callout_info",
    "futimesat": "filename",
    "newfstatat": "filename",
    "utimensat": "filename",
    "fanotify_mark": "pathname",
    "statx": "filename",
    "fsconfig": "_key",
}

# Counts here are byte counts passed in another register. Arrays of records and
# commands with a length or layout selected by a separate pointer stay explicit.
READ_BUFFERS = {
    "write": ("buf", "count"),
    "pwrite64": ("buf", "count"),
    "sendto": ("buff", "len"),
    "setsockopt": ("optval", "optlen"),
    "sethostname": ("name", "len"),
    "setdomainname": ("name", "len"),
    "init_module": ("umod", "len"),
    "setxattr": ("value", "size"),
    "lsetxattr": ("value", "size"),
    "fsetxattr": ("value", "size"),
    "mq_timedsend": ("u_msg_ptr", "msg_len"),
    "add_key": ("_payload", "plen"),
    # kexec also requires the final byte to be NUL when cmdline_len is nonzero.
    "kexec_file_load": ("cmdline_ptr", "cmdline_len"),
}
WRITE_BUFFERS = {
    "read": ("buf", "count"),
    "pread64": ("buf", "count"),
    "recvfrom": ("ubuf", "size"),
    "getcwd": ("buf", "size"),
    "readlink": ("buf", "bufsiz"),
    "readlinkat": ("buf", "bufsiz"),
    "getxattr": ("value", "size"),
    "lgetxattr": ("value", "size"),
    "fgetxattr": ("value", "size"),
    "listxattr": ("list", "size"),
    "llistxattr": ("list", "size"),
    "flistxattr": ("list", "size"),
    "mq_timedreceive": ("u_msg_ptr", "msg_len"),
    "getrandom": ("ubuf", "len"),
}

# Additional pointers with an input-only or nullable contract, as checked in
# fs/open.c, fs/utimes.c, kernel/signal.c, kernel/time and net/socket.c.
POINTERS = {
    "openat2": {"how": "ConstPtr<open_how>"},
    "mount": {"data": "Nullable<ConstPtr<Void>>"},
    "shmat": {"shmaddr": "Nullable<MutPtr<Void>>"},
    "shmdt": {"shmaddr": "ConstPtr<Void>"},
    "execve": {"argv": "Nullable<NulTerminatedArray<CString>>", "envp": "Nullable<NulTerminatedArray<CString>>"},
    "execveat": {"argv": "Nullable<NulTerminatedArray<CString>>", "envp": "Nullable<NulTerminatedArray<CString>>"},
    "accept": {"upeer_sockaddr": "Nullable<MutPtr<sockaddr>>", "upeer_addrlen": "Nullable<MutPtr<I32>>"},
    "accept4": {"upeer_sockaddr": "Nullable<MutPtr<sockaddr>>", "upeer_addrlen": "Nullable<MutPtr<I32>>"},
    "recvfrom": {"addr": "Nullable<MutPtr<sockaddr>>", "addr_len": "Nullable<MutPtr<I32>>"},
    "sendto": {"addr": "Nullable<ConstPtr<sockaddr>>"},
    "utime": {"times": "Nullable<ConstPtr<utimbuf>>"},
    "utimes": {"utimes": "Nullable<ConstPtr<__kernel_old_timeval>>"},
    "futimesat": {"utimes": "Nullable<ConstPtr<__kernel_old_timeval>>"},
    "utimensat": {"utimes": "Nullable<ConstPtr<__kernel_timespec>>"},
    "nanosleep": {"rqtp": "ConstPtr<__kernel_timespec>", "rmtp": "Nullable<MutPtr<__kernel_timespec>>"},
    "clock_nanosleep": {"rmtp": "Nullable<MutPtr<__kernel_timespec>>"},
    "rt_sigaction": {"act": "Nullable<ConstPtr<sigaction>>", "oact": "Nullable<MutPtr<sigaction>>"},
    "rt_sigprocmask": {"nset": "Nullable<ConstPtr<sigset_t>>", "oset": "Nullable<MutPtr<sigset_t>>"},
    "sigaltstack": {"uss": "Nullable<ConstPtr<stack_t>>", "uoss": "Nullable<MutPtr<stack_t>>"},
    "time": {"tloc": "Nullable<MutPtr<I64>>"},
    "gettimeofday": {"tv": "Nullable<MutPtr<__kernel_old_timeval>>", "tz": "Nullable<MutPtr<timezone>>"},
    "wait4": {"stat_addr": "Nullable<MutPtr<I32>>", "ru": "Nullable<MutPtr<rusage>>"},
    "waitid": {"infop": "Nullable<MutPtr<siginfo>>", "ru": "Nullable<MutPtr<rusage>>"},
    "timerfd_settime": {"otmr": "Nullable<MutPtr<__kernel_itimerspec>>"},
    "timer_settime": {"old_setting": "Nullable<MutPtr<__kernel_itimerspec>>"},
    "ppoll": {"tsp": "Nullable<MutPtr<__kernel_timespec>>", "sigmask": "Nullable<ConstPtr<sigset_t>>"},
    "select": {
        "inp": "Nullable<MutPtr<fd_set>>", "outp": "Nullable<MutPtr<fd_set>>",
        "exp": "Nullable<MutPtr<fd_set>>", "tvp": "Nullable<MutPtr<__kernel_old_timeval>>",
    },
    "pselect6": {
        "inp": "Nullable<MutPtr<fd_set>>", "outp": "Nullable<MutPtr<fd_set>>",
        "exp": "Nullable<MutPtr<fd_set>>", "tsp": "Nullable<MutPtr<__kernel_timespec>>",
        "sig": "Nullable<ConstPtr<Void>>",
    },
    "mq_open": {"u_attr": "Nullable<ConstPtr<mq_attr>>"},
    "mq_timedsend": {"u_abs_timeout": "Nullable<ConstPtr<__kernel_timespec>>"},
    "mq_timedreceive": {
        "u_msg_prio": "Nullable<MutPtr<U32>>", "u_abs_timeout": "Nullable<ConstPtr<__kernel_timespec>>",
    },
    "io_getevents": {"timeout": "Nullable<ConstPtr<__kernel_timespec>>"},
    "io_pgetevents": {"timeout": "Nullable<ConstPtr<__kernel_timespec>>", "usig": "Nullable<ConstPtr<__aio_sigset>>"},
}

# getsockopt takes its capacity through an in/out pointer. syslog's buffer
# exists only for read commands; other commands can ignore both buf and len.
RAW_CHAR_POINTERS = {("getsockopt", "optval"), ("syslog", "buf")}


def refinements():
    result = {}
    groups = (
        (((name, param), "CString") for name, params in STRINGS.items() for param in params.split()),
        (((name, param), "Nullable<CString>") for name, params in NULLABLE_STRINGS.items() for param in params.split()),
        (((name, param), f"ReadBuffer<{length}>") for name, (param, length) in READ_BUFFERS.items()),
        (((name, param), f"WriteBuffer<{length}>") for name, (param, length) in WRITE_BUFFERS.items()),
        (((name, param), kind) for name, params in POINTERS.items() for param, kind in params.items()),
    )
    for group in groups:
        for entry, kind in group:
            if entry in result or entry in RAW_CHAR_POINTERS:
                raise ValueError(f"multiple pointer contracts for {entry[0]}.{entry[1]}")
            result[entry] = kind
    return result
