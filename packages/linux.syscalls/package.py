#!/usr/bin/env python3
"""Resolve, review and build bounded LLMLang Linux x86-64 syscall consumers."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from contracts.contracts import CONTRACTS_PATH, load_contracts, refinement, render

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
STAGE0 = ROOT / "tools/llmlang_mvp/stage0/Cargo.toml"
PROVIDER = PACKAGE / "provider"
TARGET = "x86_64-unknown-linux-gnu"
ABI = "linux-x86_64-native"
RUST_VERSION = "1.85.1"
LOCK = PACKAGE / "snapshot"
ADMISSIONS = PACKAGE / "admissions.json"
RUNTIME = PACKAGE / "runtime.rs.in"
SNAPSHOT_PROVIDER = "linux.syscalls.package.provider"
SNAPSHOT_INPUTS = "linux.syscalls.package.inputs"
SNAPSHOT_SOURCE = "linux.syscalls.source."
SNAPSHOT_INTERFACE = "linux.syscalls.contract."
RUNTIME_EXPORTS = (
    "Advice, ChildPid, Directory, EpollControl, EpollEvent, ExecImage, LinuxFd, "
    "Mapping, OpenOptions, PollEntry, Protection, RandomMode, ReadOutcome, "
    "SeekOrigin, Shutdown, SleepOutcome, SyscallError, SystemInfo, TimerSpec, "
    "Timespec, UnmapError, UtsName, WaitStatus, CLOCK_MONOTONIC, CLOCK_REALTIME, "
    "EFD_SEMAPHORE, EINTR, EPOLLIN, EPOLLOUT, O_CLOEXEC, O_CREAT, O_EXCL, "
    "O_NONBLOCK, O_RDONLY, O_RDWR, O_WRONLY, POLLIN, POLLOUT, TFD_TIMER_ABSTIME, "
    "BpfArray, ClockSleepMode, ClockSleepOutcome, DirectoryEntry, FileMetadata, FileStat, "
    "IoUringInfo, IoUringOpcode, IoUringProbe, LimitResource, Limit, PriorityKind, "
    "ResourceUsage, Rlimit, SchedulePolicy, StatTimestamp, Timeval, UsageScope, UsageTime, UtsNamespace, "
    "CpuLocation, Datagram4, FileAdvice, MessageQueue, QueueAccess, QueueAttributes, QueueCreate, "
    "QueueLimits, QueueName, QueueOpen, ReceivedMessage, RenameMode, SyncFileRangeFlags, ThreadName, UdpSocket4, "
    "MountedTmpfs, MountNamespaceError, PrivateMountNamespace, UnmountTmpfsError, "
    "ChildPidFd, ChildSignal, ReceivedStreamMessage, XattrMode, "
    "CurrentThreadSignalScope, SignalFd, SignalEvent, SignalScopeError, UserSignal, UserSignals, "
    "CapabilitySets, CredentialIds, FileTimes, MicroTimestamp, NanoTimestamp, PosixTimer, "
    "ReceivedDatagramMessage4, TimerMode, TimerDeleteError, "
    "CpuAffinity, WriteVectorMode, SysvMessageQueue, MessageType, MessageSelection, "
    "MessageReceiveMode, ReceivedSysvMessage, QueueRemovalError, SemaphoreSet, "
    "SemaphoreOperation, SemaphoreMode, SemaphoreRemoveError, ShmSegment, ShmAttachment, ShmStat, "
    "SendDatagram4, FileSystemStat, IntervalTimer, IntervalDuration, IntervalSettings, ProcessTimes, "
    "MemoryLockMode, MemorySyncMode, LandlockRuleset, LandlockReadAccess, IoPriority, IoPriorityObservation, "
    "LegacyAioContext, AioRequestId, AioFsyncEvent, AioPipePollEvent, LsmQuery, LsmContext, DupReplacementError, "
    "Inotify, InotifyWatch, InotifyMode, InotifyEvent, WatchMask, IN_IGNORED, IN_Q_OVERFLOW, IN_ISDIR, "
    "SelectFdSet, SelectFdSets, SelectOutcome, SelectError, SpliceMode, VmspliceReadEnd, "
    "SeccompAction, SeccompNotifSizes, MountBasic, AioCancelStatus, WaitIdOutcome, WaitIdStatus, "
    "UserId, GroupId, LegacyDirectoryEntry, BlockingSignalFd, PendingUserSignals, "
    "NumaNodeMask, NumaPolicy, NumaPolicyState, CacheStatRange, CacheStat, SchedulerPolicy, SchedulerAttributes, "
    "FutexWord, FutexWaiter, TimexObservation, ClockDisciplineState, TimexSubseconds, RobustListInfo, "
    "Fanotify, FanotifyMarkAction, FanotifyMask, FanotifyEvent, SessionKeyring, OwnedUserKey, KeyReadOutcome, "
    "RobustListScopeError, ChangeRootError, ScopedFileHandle, ExecveAtImage, SealedExecutable, VforkExecError, "
    "LegacyUstat, QueueNotification, ProtectionKey, ProtectionKeyReleaseError, KnownChildDescriptor, "
    "ChildDescriptorError, SavedUtsNamespace, PinUtsError, SealedMapping, SealMappingError, SignalActionScopeError, SignalWaitEvent, SignalWaitSender, UretprobeObservation, "
    "FilePageMapping, PrivatePty, PtyHangupError, ProcessAdvice, RseqRegistration, QuotaKind, QuotaFormat, ShadowStack"
)
NATIVE_ALIASES = {
    "io_destroy": ("io_destroy", "close"),
    "io_submit_cancellable_pipe_poll": ("io_submit", "pipe2", "close"),
    "io_getevents_cancelled_pipe_poll": ("io_getevents", "close"),
    "fork_exit": ("fork", "exit"),
    "quotactl_get_format": ("quotactl",),
    "quotactl_fd_get_format": ("quotactl_fd",),
    "finit_module": ("fcntl", "fstat", "finit_module"),
    "rseq_unregister": ("rseq",),
    "create_file_page_mapping": ("memfd_create", "write", "fcntl", "mmap", "close", "munmap"),
    "exit_group_without_clear_tid": ("set_tid_address", "exit_group"),
    "kexec_load_unload": ("kexec_load",),
    "kexec_file_unload": ("kexec_file_load",),
    "migrate_pages": ("get_mempolicy", "migrate_pages"),
    "process_madvise": ("getpid", "pidfd_open", "process_madvise", "close"),
    "vhangup_private_pty": ("fsopen", "fsconfig", "fsmount", "openat", "ioctl", "setsid", "vhangup", "close"),
    "fork_execve": ("fork", "execve", "exit"),
    "fcntl_getfd": ("fcntl",),
    "fcntl_getfl": ("fcntl",),
    "ioctl_fionread": ("ioctl",),
    "prctl_get_no_new_privs": ("prctl",),
    "dup_cloexec": ("fcntl",),
    "unshare_uts": ("unshare",),
    "bpf_map_create_u64": ("bpf",),
    "bpf_map_lookup_u64": ("bpf",),
    "bpf_map_update_u64": ("bpf",),
    "getsockopt_type": ("getsockopt",),
    "getsockopt_reuseaddr": ("getsockopt",),
    "setsockopt_reuseaddr": ("setsockopt",),
    "perf_event_open_task_clock": ("perf_event_open",),
    "uretprobe": ("uretprobe", "openat", "fstatfs", "fstat", "read", "perf_event_open", "close"),
    "io_uring_register_probe": ("io_uring_register",),
    "io_uring_nop": ("io_uring_setup", "mmap", "io_uring_enter", "munmap", "close"),
    "signalfd_read": ("read",),
    "read_inotify_events": ("read",),
    "setfsuid_query": ("setfsuid",),
    "setfsgid_query": ("setfsgid",),
    "sendmsg_udp4": ("sendmsg",),
    "recvmsg_udp4": ("recvmsg",),
    "sendmmsg_udp4": ("sendmmsg",),
    "recvmmsg_udp4": ("recvmmsg",),
    "setpgid_self": ("setpgid",),
    "semctl_getval": ("semctl",),
    "semctl_setval": ("semctl",),
    "semctl_remove": ("semctl",),
    "shmctl_stat": ("shmctl",),
    "shmctl_rmid": ("shmctl",),
    "io_submit_fsync": ("io_submit",),
    "ioprio_get_current": ("ioprio_get",),
    "ioprio_set_current": ("ioprio_set",),
    "setpriority_current": ("setpriority",),
    "landlock_create_ruleset_version": ("landlock_create_ruleset",),
    "openat2_beneath": ("openat2",),
    "brk_query": ("brk",),
    "vmsplice_pipe": ("pipe2",),
    "seccomp_get_action_avail": ("seccomp",),
    "seccomp_get_notif_sizes": ("seccomp",),
    "signalfd_read_blocking": ("read",),
    "tkill": ("gettid", "tkill"),
    "tgkill": ("getpid", "gettid", "tgkill"),
    "get_mempolicy_mapping": ("get_mempolicy",),
    "get_mempolicy_allowed": ("get_mempolicy",),
    "prctl_set_no_new_privs": ("prctl",),
    "capset_clear": ("capset",),
    "close_range_cloexec": ("close_range",),
    "process_vm_readv": ("getpid", "process_vm_readv"),
    "process_vm_writev": ("getpid", "process_vm_writev"),
    "futex_wait_private": ("futex",),
    "futex_wake_private": ("futex",),
    "syslog_buffer_size": ("syslog",),
    "sysfs_count": ("sysfs",),
    "mlockall_current_onfault": ("mlockall",),
    "clone_execve": ("clone", "execve", "exit"),
    "clone3_execve": ("clone3", "execve", "exit"),
    "read_fanotify_event": ("read",),
    "keyctl_join_session": ("keyctl",),
    "keyctl_read": ("keyctl",),
    "keyctl_unlink": ("keyctl",),
    "arch_prctl_get_fs": ("arch_prctl",),
    "arch_prctl_get_gs": ("arch_prctl",),
    "modify_ldt_read": ("modify_ldt",),
    "iopl_drop": ("iopl",),
    "ioperm_revoke": ("ioperm",),
    "chroot_tmpfs": ("openat", "fchdir", "chroot", "close"),
    "pivot_root_tmpfs": ("openat", "fchdir", "pivot_root", "close"),
    "set_robust_list": ("set_robust_list", "get_robust_list"),
    "name_to_handle_at": ("openat2", "fstat", "name_to_handle_at", "close"),
    "reboot_cad_control": ("reboot",),
    "prepare_execveat_fd": ("memfd_create", "write", "fcntl", "close"),
    "fork_execveat": ("fork", "execveat", "exit"),
    "vfork_execve_masked": ("rt_sigprocmask", "vfork", "execve", "exit"),
    "ustat": ("fstat", "ustat"),
    "kcmp": ("getpid", "kcmp"),
    "pidfd_getfd": ("pidfd_getfd", "getpid", "kcmp", "close"),
    "unshare_uts_pinned": ("fsopen", "fsconfig", "fsmount", "unshare", "openat", "close"),
    "setns_uts": ("setns",),
    "ptrace_trace_me": ("ptrace",),
    "rt_sigaction": ("pipe2", "rt_sigprocmask", "fork", "rt_sigaction", "getpid", "tgkill", "rt_sigreturn", "write", "exit", "wait4", "close", "read"),
    "sigaltstack": ("pipe2", "rt_sigprocmask", "fork", "rt_sigaction", "getpid", "tgkill", "rt_sigreturn", "sigaltstack", "write", "exit", "wait4", "close", "read"),
    "pause": ("pipe2", "rt_sigprocmask", "fork", "rt_sigaction", "setitimer", "getitimer", "pause", "rt_sigreturn", "write", "exit", "wait4", "close", "read"),
    "rt_sigsuspend": ("pipe2", "rt_sigprocmask", "fork", "rt_sigaction", "getpid", "tgkill", "rt_sigpending", "rt_sigsuspend", "rt_sigreturn", "write", "exit", "wait4", "close", "read"),
    "rt_sigqueueinfo": ("pipe2", "rt_sigprocmask", "fork", "getpid", "getuid", "rt_sigqueueinfo", "rt_sigtimedwait", "write", "exit", "wait4", "close", "read"),
    "rt_tgsigqueueinfo": ("pipe2", "rt_sigprocmask", "fork", "getpid", "getuid", "rt_tgsigqueueinfo", "rt_sigtimedwait", "write", "exit", "wait4", "close", "read"),
    "membarrier_query": ("membarrier",),
    "personality_query": ("personality",),
    "prctl_get_name": ("prctl",),
    "prctl_set_name": ("prctl",),
    "socket_udp4": ("socket",),
    "bind_udp4": ("bind",),
    "connect_udp4": ("connect",),
    "getsockname_udp4": ("getsockname",),
    "sendto_udp4": ("sendto",),
    "recvfrom_udp4": ("recvfrom",),
    "unshare_mount_private": ("unshare", "mount"),
    "mount_tmpfs": ("fsopen", "fsconfig", "fsmount", "move_mount", "close"),
    "umount2_tmpfs": ("openat", "fchdir", "umount2", "close"),
}
APP_MANIFEST = """[package]
name = "llmlang-syscall-app"
version = "0.1.0"
edition = "2021"

[dependencies]
linux-syscalls-provider = { path = "provider", package = "linux_syscalls_provider" }

[profile.release]
overflow-checks = true
"""


class PackageError(Exception):
    pass


def digest(domain, value):
    return "sha256:" + hashlib.sha256(domain.encode() + b"\0" + canonical(value)).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def file_hash(data):
    return hashlib.sha256(data).hexdigest()


def command(arguments, *, cwd=None, timeout=180):
    try:
        result = subprocess.run(
            arguments, cwd=cwd or ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PackageError(f"{arguments[0]}: {error}") from error
    if result.returncode:
        raise PackageError(result.stderr.strip() or result.stdout.strip() or f"{arguments[0]} failed")
    return result.stdout


def provider_files(directory=PROVIDER):
    sources = [directory / "Cargo.toml", *sorted((directory / "src").rglob("*.rs"))]
    if len(sources) < 2:
        raise PackageError("missing provider source")
    return {file.relative_to(directory).as_posix(): file.read_bytes() for file in sources}


def archived_provider(path):
    from storage import load_record

    record = load_record(path, SNAPSHOT_PROVIDER)
    if set(record) != {"schema", "files"} or record["schema"] not in {
        "llmlang.linux.syscalls.provider.v1", "llmlang.linux.syscalls.provider.v2",
    }:
        raise PackageError("unsupported archived provider schema")
    files = {}
    for name, value in record["files"].items():
        relative = PurePosixPath(name)
        if relative.as_posix() != name or not (
            name == "Cargo.toml"
            or (relative.parts[:1] == ("src",) and ".." not in relative.parts and relative.suffix == ".rs")
        ):
            raise PackageError(f"invalid archived provider path: {name}")
        if record["schema"].endswith(".v2"):
            source = load_record(path, SNAPSHOT_SOURCE + "provider." + name)
            contents = base64.b64decode(source["base64"], validate=True)
            if file_hash(contents) != value:
                raise PackageError(f"archived provider file hash mismatch: {name}")
        else:
            contents = base64.b64decode(value, validate=True)
        files[name] = contents
    if not {"Cargo.toml", "src/lib.rs"} <= files.keys():
        raise PackageError("incomplete archived provider")
    return files


def verify_native_numbers(entries, files):
    constants = {}
    for path, data in files.items():
        if not path.endswith(".rs"):
            continue
        for name, number in re.findall(r"(?m)^(?:pub(?:\([^\n]+\))? )?const ([A-Z0-9_]+): usize = ([0-9]+);", data.decode()):
            constants.setdefault(name, []).append(int(number))
    for name, number in entries.items():
        actual = constants.get(name.upper())
        if actual != [number]:
            raise PackageError(f"native ABI number mismatch for {name}: expected {number}, found {actual}")


def current_bindings(operations, files):
    from catalog.catalog import load_catalog

    catalog = load_catalog()
    native_rows = {record["name"]: record["number"] for record in catalog["syscalls"]}
    provider = {path: file_hash(data) for path, data in files.items()}
    bindings = {}
    required_numbers = {}
    for name, operation in operations.items():
        entries = NATIVE_ALIASES.get(name, (name,))
        if any(entry not in native_rows for entry in entries):
            raise PackageError(f"contract {name} has no entry in the pinned native catalog")
        entries = {entry: native_rows[entry] for entry in entries}
        required_numbers.update(entries)
        public = operation.public.id
        provided = operation.provided.id
        subject = {
            "symbol": name,
            "provider_files": provider,
            "native_entries": entries,
            "target_abi": ABI,
            "target": TARGET,
            "kernel_catalog": catalog["kernel"],
            "rust_toolchain": RUST_VERSION,
            "provided_contract": provided,
        }
        bindings[name] = {
            "qualified_name": f"linux.syscalls.{name}",
            "interface_revision": operation.interface_revision,
            "signature": operation.public.signature,
            "required_contract": public,
            "public_contract": public,
            "provided_contract": provided,
            "target": TARGET,
            "target_abi": ABI,
            "impl_hash": digest("llmlang.linux.syscalls.impl.v1", subject),
            "implementation": subject,
        }
    verify_native_numbers(required_numbers, files)
    return bindings


def archived_inputs(path, names):
    from storage import load_record

    record = load_record(path, SNAPSHOT_INPUTS)
    if record.get("schema") == "llmlang.linux.syscalls.package.inputs.v1":
        data = base64.b64decode(record["contracts"], validate=True)
    elif record.get("schema") == "llmlang.linux.syscalls.package.inputs.v2":
        types = load_record(path, SNAPSHOT_SOURCE + "contracts.types")
        selected = [load_record(path, SNAPSHOT_SOURCE + "contracts." + name) for name in names]
        if {item["name"] for item in selected} != set(names):
            raise PackageError("archived contract name mismatch")
        data = canonical({**types, "operations": selected})
    else:
        raise PackageError("unsupported archived package inputs schema")
    with tempfile.TemporaryDirectory(prefix="llmlang-syscall-contracts-") as temporary:
        source = Path(temporary) / "syscalls.json"
        source.write_bytes(data)
        return load_contracts(source), record["evidence_inputs"]


def read_lock(path, names):
    if path.is_dir():
        from storage import load_record

        return {name: load_record(path, f"linux.syscalls.{name}") for name in names}
    # A canonical JSON lock is useful for inspecting and testing a selection.
    data = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    if (
        not isinstance(data, dict)
        or set(data) != {"schema", "bindings"}
        or data["schema"] != "llmlang.linux.syscalls.lock.v1"
        or not isinstance(data["bindings"], dict)
    ):
        raise PackageError("unsupported binding lock schema")
    return data["bindings"]


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackageError(f"ambiguous duplicate key in input: {key}")
        result[key] = value
    return result


def resolve(names, pinned, available):
    resolved = {}
    for name in sorted(names):
        if name not in pinned:
            raise PackageError(f"missing pinned binding for linux.syscalls.{name}")
        if name not in available:
            raise PackageError(f"provider unavailable for linux.syscalls.{name}")
        if pinned[name] != available[name]:
            raise PackageError(f"stale or mismatched binding for linux.syscalls.{name}")
        resolved[name] = pinned[name]
    return resolved


def evidence_inputs():
    paths = sorted((PACKAGE / "evidence").glob("*"))
    paths += sorted((PROVIDER / "examples").glob("*.rs"))
    paths += sorted((PROVIDER / "tests").rglob("*.rs"))
    paths += sorted((PACKAGE / "guest").glob("*"))
    return {
        path.relative_to(PACKAGE).as_posix(): file_hash(path.read_bytes())
        for path in paths if path.is_file() and path.suffix in (".lean", ".bpl", ".py", ".rs", ".json", ".c")
    }


def admission_identity(binding, evidence_files):
    envelope = {
        "binding": binding,
        "profile": "linux-syscalls-bounded-native-v1",
        "evidence_files": evidence_files,
        "rust": RUST_VERSION,
    }
    return digest("llmlang.linux.syscalls.admission.v1", envelope)


def check_evidence(bindings, operations, path=ADMISSIONS, *, fingerprints=None, report_rejections=False):
    admissions = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    if not isinstance(admissions, dict) or admissions.get("schema") != "llmlang.linux.syscalls.admissions.v1":
        raise PackageError("unsupported admission schema")
    evidence_files = evidence_inputs() if fingerprints is None else fingerprints
    releases = [
        release["operations"]
        for release in [admissions, *admissions.get("history", [])]
        if release.get("evidence_inputs", evidence_files) == evidence_files
    ]
    result = {}
    for name, binding in bindings.items():
        try:
            result[name] = admit_operation(name, binding, operations[name], evidence_files, releases)
        except PackageError as error:
            if not report_rejections:
                raise
            result[name] = {"diagnostic": str(error)}
    return result


def admit_operation(name, binding, operation, evidence_files, releases):
    violations = refinement(operation.public, operation.provided)
    if violations:
        raise PackageError(f"provided contract does not refine linux.syscalls.{name}: {violations}")
    subject = admission_identity(binding, evidence_files)
    record = next(
        (release[name] for release in releases if release.get(name, {}).get("subject") == subject),
        None,
    )
    if record is None:
        raise PackageError(f"missing or stale exact evidence for linux.syscalls.{name}")
    if record.get("body") not in {"BOUNDED_NATIVE_TEST", "BOUNDED_DISPOSABLE_VM_TEST"} or not record.get("cases"):
        raise PackageError(f"provider conformance evidence unavailable for linux.syscalls.{name}")
    return {
        "public_refinement": "EXACT_CLAUSE_INCLUSION",
        "formal_model": record.get("formal_model", "UNSUPPORTED"),
        "provider_conformance": record["body"],
        "native_cases": record.get("host_cases", record["cases"]),
        "guest_cases": record["cases"] if "guest_kernel" in record else [],
        "kernel_behavior": "EXTERNAL_ASSUMPTIONS",
        "scope": "bounded syscall adapter profile",
        "guest_kernel": record.get("guest_kernel"),
        "subject": record["subject"],
    }


def rust_tools():
    version = command(["rustc", "-Vv"])
    if not version.startswith(f"rustc {RUST_VERSION} ") or f"host: {TARGET}" not in version.splitlines():
        raise PackageError(f"the profile requires Rust {RUST_VERSION} hosted on {TARGET}")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise PackageError(f"unsupported host for {ABI}")
    return version


def stage0(source):
    settings = ["--manifest-path", str(STAGE0), "--locked", "--offline"]
    raw = command(
        ["cargo", "run", *settings, "--quiet", "--", "parse-syscalls", str(source.resolve())]
    )
    return json.loads(raw)


def graph(module, selected):
    semantic = {
        "schema": "llmlang.syscalls.spg.v1",
        "profile": "stage0-native-io-v1",
        "target": TARGET,
        "runtime": file_hash(RUNTIME.read_bytes()),
        "module": module["body"],
        "bindings": selected,
        "provider_symbols": sorted(set(module["symbols"]) & set(RUNTIME_EXPORTS.split(", "))),
        "calls": [
            {
                "qualified_name": selected[call["name"]]["qualified_name"],
                "impl_hash": selected[call["name"]]["impl_hash"],
                "required_contract": selected[call["name"]]["required_contract"],
            }
            for call in module["calls"]
        ],
    }
    return {
        **semantic,
        "content_hash": digest("llmlang.linux.syscalls.spg.v1", semantic),
        "call_spans": [
            {"line": call["line"], "column": call["column"]} for call in module["calls"]
        ],
    }


def native(graph_record, files, output=None):
    # The Stage 0 validator admits only a closed profile. The Rust type checker
    # then checks the generated code, including moves and borrowed lifetimes.
    with tempfile.TemporaryDirectory(prefix="llmlang-syscalls-") as temporary:
        workspace = Path(temporary)
        (workspace / "src").mkdir()
        (workspace / "Cargo.toml").write_text(APP_MANIFEST, encoding="utf-8")
        for name, data in files.items():
            location = workspace / "provider" / name
            location.parent.mkdir(parents=True, exist_ok=True)
            location.write_bytes(data)
        runtime = RUNTIME.read_bytes()
        if file_hash(runtime) != graph_record["runtime"]:
            raise PackageError("stage 0 runtime changed after lowering")
        imports = ", ".join(sorted({*graph_record["bindings"], *graph_record["provider_symbols"]}))
        main = (
            runtime.decode() + f"\nuse linux_syscalls_provider::{{{imports}}};\n"
            + graph_record["module"] + "\n"
        )
        (workspace / "src/main.rs").write_text(main, encoding="utf-8")
        command(["cargo", "generate-lockfile", "--offline"], cwd=workspace)
        action = "build" if output is not None else "check"
        flags = [
            "--target", TARGET, "--target-dir", str(workspace / "target"),
            "--quiet", "--offline", "--locked", "--release",
        ]
        command(["cargo", action, *flags], cwd=workspace)
        if output is not None:
            artifact = workspace / "target" / TARGET / "release/llmlang-syscall-app"
            output.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp_output = tempfile.mkstemp(prefix=f".{output.name}-", dir=output.parent)
            os.close(descriptor)
            try:
                shutil.copy2(artifact, temp_output)
                os.replace(temp_output, output)
            finally:
                Path(temp_output).unlink(missing_ok=True)


def output_json(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for action in ("review", "check", "spg", "build"):
        sub = actions.add_parser(action)
        sub.add_argument("source", type=Path)
        sub.add_argument("--lock", type=Path, default=LOCK)
        if action == "build":
            sub.add_argument("-o", "--output", type=Path, required=True)
    export = actions.add_parser("export-lock", help="write proposed bindings; this does not grant admission")
    export.add_argument("output", type=Path)
    export.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.action == "export-lock":
            operations = load_contracts()
            files = provider_files()
            available = current_bindings(operations, files)
            if args.json:
                with args.output.open("xb") as stream:
                    stream.write(canonical({"schema": "llmlang.linux.syscalls.lock.v1", "bindings": available}) + b"\n")
            else:
                from storage import export_records

                records = {binding["qualified_name"]: binding for binding in available.values()}
                records[SNAPSHOT_PROVIDER] = {
                    "schema": "llmlang.linux.syscalls.provider.v2",
                    "files": {name: file_hash(data) for name, data in files.items()},
                }
                records.update({
                    SNAPSHOT_SOURCE + "provider." + name: {"base64": base64.b64encode(data).decode()}
                    for name, data in files.items()
                })
                records[SNAPSHOT_INPUTS] = {
                    "schema": "llmlang.linux.syscalls.package.inputs.v2",
                    "evidence_inputs": evidence_inputs(),
                }
                contract_source = json.loads(CONTRACTS_PATH.read_bytes(), object_pairs_hook=unique_object)
                source_operations = contract_source.pop("operations")
                records[SNAPSHOT_SOURCE + "contracts.types"] = contract_source
                records.update({
                    SNAPSHOT_SOURCE + "contracts." + item["name"]: item
                    for item in source_operations
                })
                records.update({SNAPSHOT_INTERFACE + name: render(op) for name, op in operations.items()})
                export_records(records, args.output)
            return 0

        version = rust_tools()
        parsed = stage0(args.source)
        names = parsed["imports"]
        if args.lock.is_dir():
            files = archived_provider(args.lock)
            operations, fingerprints = archived_inputs(args.lock, names)
        else:
            files = provider_files()
            operations, fingerprints = load_contracts(), None
        available = current_bindings(operations, files)
        selected = resolve(names, read_lock(args.lock, names), available)
        if args.lock.is_dir():
            from storage import load_record

            for name in names:
                if load_record(args.lock, SNAPSHOT_INTERFACE + name) != render(operations[name]):
                    raise PackageError(f"stale or mismatched interface record for linux.syscalls.{name}")
        lowered = graph(parsed, selected)
        if args.action == "review":
            evidence = {}
            for name, binding in selected.items():
                try:
                    evidence.update(check_evidence({name: binding}, operations, fingerprints=fingerprints))
                except (OSError, ValueError, PackageError) as error:
                    evidence[name] = {"status": "NOT_ADMITTED", "diagnostic": str(error)}
        else:
            evidence = check_evidence(selected, operations, fingerprints=fingerprints)
        if args.action != "review" or all(item.get("status") != "NOT_ADMITTED" for item in evidence.values()):
            native(lowered, files, args.output if args.action == "build" else None)
        if args.action == "spg":
            output_json(lowered)
        elif args.action == "review":
            output_json({
                "spg": lowered["content_hash"],
                "abi": ABI,
                "interfaces": {name: render(operations[name]) for name in names},
                "bindings": selected,
                "admission": evidence,
                "call_spans": lowered["call_spans"],
            })
        elif args.action == "check":
            output_json({
                "spg": lowered["content_hash"],
                "abi": ABI,
                "rust": version,
                "admission": evidence,
            })
    except (PackageError, OSError, ValueError, KeyError, ImportError) as error:
        print(f"linux.syscalls: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
