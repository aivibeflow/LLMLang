// Stage 0 source profile for native syscall consumers.
use std::collections::BTreeSet;

use quote::ToTokens;
use serde::Serialize;
use syn::spanned::Spanned;
use syn::visit::{self, Visit};
use syn::{Expr, Item, Pat, Type};

const INTRINSICS: &[&str] = &[
    "stdin_fd",
    "stdout_fd",
    "cli_paths",
    "process_exit",
    "loopback_ephemeral",
];
const CONSTRUCTORS: &[&str] = &[
    "Ok",
    "Err",
    "Some",
    "CString::new",
    "SocketAddrV4::new",
    "Ipv4Addr::new",
    "IoSlice::new",
    "IoSliceMut::new",
    "Timespec::new",
    "Timeval::new",
    "MicroTimestamp::new",
    "NanoTimestamp::exact",
    "CpuAffinity::single",
    "SelectFdSet::new",
    "SelectFdSets::new",
    "UserId::new",
    "GroupId::new",
    "FutexWord::new",
    "FutexWaiter::new",
    "NumaNodeMask::from_nodes",
    "NumaPolicy::Bind",
    "NumaPolicy::Interleave",
    "IntervalDuration::new",
    "IoPriority::BestEffort",
    "MessageType::new",
    "MessageSelection::Exact",
    "QueueLimits::new",
    "QueueName::new",
    "EpollControl::Add",
    "EpollControl::Modify",
    "Directory::Borrowed",
    "PollEntry::new",
    "ExecImage::new",
    "ExecveAtImage::new",
    "QuotaFormat::Unknown",
    "KnownChildDescriptor::new",
    "i32::from",
];
const METHODS: &[&str] = &[
    "as_c_str",
    "as_slice",
    "as_mut_slice",
    "as_bytes",
    "len",
    "is_empty",
    "into",
    "port",
    "cpu_id",
    "borrow",
    "is_errno",
    "returned",
    "exited",
    "pid",
    "seconds",
    "nanos",
    "micros",
    "length",
    "protection",
    "into_parts",
    "into_fd",
    "combine",
    "truncated",
    "value",
    "first",
    "contains",
    "insert",
    "load",
    "store",
    "count",
    "descriptor",
    "mount_id",
    "bits",
    "max_messages",
    "max_message_size",
    "system",
    "node",
    "release",
    "version",
    "machine",
    "domain",
    "to_bytes",
];
const TYPES: &[&str] = &[
    "bool",
    "u8",
    "u16",
    "u32",
    "u64",
    "usize",
    "i16",
    "i32",
    "i64",
    "isize",
    "str",
    "Result",
    "Option",
    "Box",
    "CString",
    "CStr",
    "BorrowedFd",
    "LinuxFd",
    "ReadOutcome",
    "Vec",
    "BpfArray",
    "ClockSleepMode",
    "ClockSleepOutcome",
    "FileMetadata",
    "DirectoryEntry",
    "FileStat",
    "IoUringInfo",
    "IoUringOpcode",
    "IoUringProbe",
    "LimitResource",
    "Limit",
    "PriorityKind",
    "ResourceUsage",
    "Rlimit",
    "SchedulePolicy",
    "StatTimestamp",
    "Timeval",
    "UsageScope",
    "UsageTime",
    "UtsNamespace",
    "CpuLocation",
    "Datagram4",
    "FileAdvice",
    "MessageQueue",
    "QueueAccess",
    "QueueAttributes",
    "QueueCreate",
    "QueueLimits",
    "QueueName",
    "QueueOpen",
    "ReceivedMessage",
    "RenameMode",
    "SyncFileRangeFlags",
    "ThreadName",
    "UdpSocket4",
    "MountedTmpfs",
    "MountNamespaceError",
    "ChildPidFd",
    "ChildSignal",
    "ReceivedStreamMessage",
    "XattrMode",
    "CapabilitySets",
    "CredentialIds",
    "FileTimes",
    "MicroTimestamp",
    "NanoTimestamp",
    "PosixTimer",
    "TimerMode",
    "TimerDeleteError",
    "ReceivedDatagramMessage4",
    "SendDatagram4",
    "FileSystemStat",
    "IntervalTimer",
    "IntervalDuration",
    "IntervalSettings",
    "ProcessTimes",
    "MemoryLockMode",
    "MemorySyncMode",
    "LandlockRuleset",
    "LandlockReadAccess",
    "IoPriority",
    "IoPriorityObservation",
    "LegacyAioContext",
    "AioRequestId",
    "AioFsyncEvent",
    "AioPipePollEvent",
    "LsmQuery",
    "LsmContext",
    "DupReplacementError",
    "Inotify",
    "InotifyWatch",
    "InotifyMode",
    "InotifyEvent",
    "WatchMask",
    "SelectFdSet",
    "SelectFdSets",
    "SelectOutcome",
    "SelectError",
    "SpliceMode",
    "VmspliceReadEnd",
    "SeccompAction",
    "SeccompNotifSizes",
    "MountBasic",
    "AioCancelStatus",
    "WaitIdOutcome",
    "WaitIdStatus",
    "UserId",
    "GroupId",
    "LegacyDirectoryEntry",
    "BlockingSignalFd",
    "PendingUserSignals",
    "NumaNodeMask",
    "NumaPolicy",
    "NumaPolicyState",
    "CacheStatRange",
    "CacheStat",
    "SchedulerPolicy",
    "SchedulerAttributes",
    "FutexWord",
    "FutexWaiter",
    "TimexObservation",
    "ClockDisciplineState",
    "TimexSubseconds",
    "RobustListScopeError",
    "ChangeRootError",
    "ScopedFileHandle",
    "ExecveAtImage",
    "SealedExecutable",
    "VforkExecError",
    "LegacyUstat",
    "QueueNotification",
    "ProtectionKey",
    "ProtectionKeyReleaseError",
    "KnownChildDescriptor",
    "ChildDescriptorError",
    "SavedUtsNamespace",
    "PinUtsError",
    "SealedMapping",
    "SealMappingError",
    "SignalActionScopeError",
    "SignalWaitEvent",
    "SignalWaitSender",
    "FilePageMapping",
    "PrivatePty",
    "PtyHangupError",
    "ProcessAdvice",
    "RseqRegistration",
    "QuotaKind",
    "QuotaFormat",
    "UretprobeObservation",
    "ShadowStack",
    "RobustListInfo",
    "Fanotify",
    "FanotifyMarkAction",
    "FanotifyMask",
    "FanotifyEvent",
    "SessionKeyring",
    "OwnedUserKey",
    "KeyReadOutcome",
    "CpuAffinity",
    "WriteVectorMode",
    "SysvMessageQueue",
    "MessageType",
    "MessageSelection",
    "MessageReceiveMode",
    "ReceivedSysvMessage",
    "QueueRemovalError",
    "SemaphoreSet",
    "SemaphoreOperation",
    "SemaphoreMode",
    "SemaphoreRemoveError",
    "ShmSegment",
    "ShmAttachment",
    "ShmStat",
    "CurrentThreadSignalScope",
    "SignalFd",
    "SignalEvent",
    "SignalScopeError",
    "UserSignal",
    "UserSignals",
    "PrivateMountNamespace",
    "UnmountTmpfsError",
    "SyscallError",
    "PollEntry",
    "Directory",
    "OpenOptions",
    "SocketAddrV4",
    "ExecImage",
    "ChildPid",
    "WaitStatus",
    "std::error::Error",
    "Ipv4Addr",
    "IoSlice",
    "IoSliceMut",
    "Mapping",
    "Protection",
    "Advice",
    "UnmapError",
    "Timespec",
    "TimerSpec",
    "SleepOutcome",
    "EpollEvent",
    "EpollControl",
    "Shutdown",
    "UtsName",
    "SystemInfo",
    "RandomMode",
    "SeekOrigin",
];
const VALUES: &[&str] = &[
    "Ok",
    "Err",
    "Some",
    "None",
    "ReadOutcome::Eof",
    "ReadOutcome::Progress",
    "Directory::Current",
    "Ipv4Addr::LOCALHOST",
    "Protection::ReadOnly",
    "Protection::ReadWrite",
    "Advice::Normal",
    "Advice::Random",
    "Advice::Sequential",
    "Advice::WillNeed",
    "Advice::DontNeed",
    "SleepOutcome::Completed",
    "LsmQuery::Complete",
    "SeccompAction::KillProcess",
    "SeccompAction::KillThread",
    "SeccompAction::Trap",
    "SeccompAction::Errno",
    "SeccompAction::UserNotify",
    "SeccompAction::Trace",
    "SeccompAction::Log",
    "SeccompAction::Allow",
    "FanotifyMarkAction::Add",
    "FanotifyMarkAction::Remove",
    "FanotifyMask::ACCESS",
    "FanotifyMask::MODIFY",
    "FanotifyMask::CLOSE_WRITE",
    "FanotifyMask::CLOSE_NOWRITE",
    "FanotifyMask::OPEN",
    "KeyReadOutcome::Written",
    "NumaPolicy::Default",
    "NumaPolicy::Local",
    "NumaPolicy::Bind",
    "NumaPolicy::Interleave",
    "SchedulerPolicy::Normal",
    "SchedulerPolicy::Batch",
    "SchedulerPolicy::Idle",
    "SpliceMode::Blocking",
    "SpliceMode::NonBlocking",
    "AioCancelStatus::CompletionPending",
    "WaitIdOutcome::Exited",
    "InotifyMode::Blocking",
    "InotifyMode::NonBlocking",
    "WatchMask::ACCESS",
    "WatchMask::MODIFY",
    "WatchMask::ATTRIB",
    "WatchMask::CLOSE_WRITE",
    "WatchMask::CLOSE_NOWRITE",
    "WatchMask::OPEN",
    "WatchMask::MOVED_FROM",
    "WatchMask::MOVED_TO",
    "WatchMask::CREATE",
    "WatchMask::DELETE",
    "WatchMask::DELETE_SELF",
    "WatchMask::MOVE_SELF",
    "IN_IGNORED",
    "IN_Q_OVERFLOW",
    "IN_ISDIR",
    "IntervalTimer::Real",
    "IntervalTimer::Virtual",
    "IntervalTimer::Profile",
    "MemoryLockMode::Immediate",
    "MemoryLockMode::OnFault",
    "MemorySyncMode::Asynchronous",
    "MemorySyncMode::Synchronous",
    "MemorySyncMode::AsynchronousInvalidate",
    "MemorySyncMode::SynchronousInvalidate",
    "LandlockReadAccess::Files",
    "LandlockReadAccess::Directories",
    "LandlockReadAccess::FilesAndDirectories",
    "IoPriority::Normal",
    "IoPriority::BestEffort",
    "IoPriority::Idle",
    "WriteVectorMode::Default",
    "WriteVectorMode::Append",
    "MessageSelection::First",
    "MessageSelection::Exact",
    "MessageReceiveMode::RequireFit",
    "MessageReceiveMode::Truncate",
    "SemaphoreMode::Wait",
    "SemaphoreMode::NoWait",
    "NanoTimestamp::NOW",
    "NanoTimestamp::OMIT",
    "TimerMode::Relative",
    "TimerMode::Absolute",
    "ClockSleepMode::Absolute",
    "ClockSleepMode::Relative",
    "ClockSleepOutcome::Completed",
    "LimitResource::Cpu",
    "LimitResource::FileSize",
    "LimitResource::Data",
    "LimitResource::Stack",
    "LimitResource::Core",
    "LimitResource::ResidentSet",
    "LimitResource::Processes",
    "LimitResource::OpenFiles",
    "LimitResource::LockedMemory",
    "LimitResource::AddressSpace",
    "LimitResource::Locks",
    "LimitResource::PendingSignals",
    "LimitResource::MessageQueue",
    "LimitResource::Nice",
    "LimitResource::RealtimePriority",
    "LimitResource::RealtimeTime",
    "Limit::Finite",
    "Limit::Unlimited",
    "PriorityKind::Process",
    "PriorityKind::ProcessGroup",
    "PriorityKind::User",
    "UsageScope::Children",
    "UsageScope::Process",
    "UsageScope::CallingThread",
    "EpollControl::Delete",
    "Shutdown::Read",
    "Shutdown::Write",
    "Shutdown::Both",
    "RandomMode::Blocking",
    "RandomMode::Nonblocking",
    "FileAdvice::Normal",
    "FileAdvice::Random",
    "FileAdvice::Sequential",
    "FileAdvice::WillNeed",
    "FileAdvice::DontNeed",
    "FileAdvice::NoReuse",
    "UserSignals::USER1",
    "UserSignals::USER2",
    "UserSignals::BOTH",
    "UserSignal::User1",
    "UserSignal::User2",
    "XattrMode::Upsert",
    "XattrMode::Create",
    "XattrMode::Replace",
    "ChildSignal::Check",
    "ChildSignal::Terminate",
    "ProcessAdvice::WillNeed",
    "ProcessAdvice::Cold",
    "QuotaKind::User",
    "QuotaKind::Group",
    "QuotaKind::Project",
    "QuotaFormat::VfsOld",
    "QuotaFormat::VfsV0",
    "QuotaFormat::Ocfs2",
    "QuotaFormat::VfsV1",
    "QuotaFormat::Shmem",
    "QuotaFormat::Unknown",
    "QueueNotification::RegisterNone",
    "QueueNotification::Unregister",
    "QueueAccess::ReadOnly",
    "QueueAccess::WriteOnly",
    "QueueAccess::ReadWrite",
    "RenameMode::Replace",
    "RenameMode::NoReplace",
    "RenameMode::Exchange",
    "SyncFileRangeFlags::NONE",
    "SyncFileRangeFlags::WAIT_BEFORE",
    "SyncFileRangeFlags::WRITE",
    "SyncFileRangeFlags::WAIT_AFTER",
    "SeekOrigin::Start",
    "SeekOrigin::Current",
    "SeekOrigin::End",
    "EINTR",
    "O_RDONLY",
    "O_WRONLY",
    "O_CREAT",
    "O_EXCL",
    "POLLIN",
    "POLLOUT",
    "O_NONBLOCK",
    "O_CLOEXEC",
    "O_RDWR",
    "CLOCK_REALTIME",
    "CLOCK_MONOTONIC",
    "EPOLLIN",
    "EPOLLOUT",
    "TFD_TIMER_ABSTIME",
    "EFD_SEMAPHORE",
];

#[derive(Serialize)]
struct Call {
    name: String,
    line: usize,
    column: usize,
}

#[derive(Serialize)]
pub struct Module {
    pub imports: BTreeSet<String>,
    symbols: BTreeSet<String>,
    body: String,
    calls: Vec<Call>,
}

fn path_name(path: &syn::Path) -> String {
    let mut parts: Vec<_> = path
        .segments
        .iter()
        .map(|segment| segment.ident.to_string())
        .collect();
    if path.leading_colon.is_some() {
        parts.insert(0, String::new());
    }
    parts.join("::")
}

fn identifier(text: &str) -> bool {
    let mut bytes = text.bytes();
    matches!(bytes.next(), Some(b'a'..=b'z' | b'A'..=b'Z' | b'_'))
        && bytes.all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
        && syn::parse_str::<syn::Ident>(text).is_ok()
}

struct Profile {
    imports: BTreeSet<String>,
    functions: BTreeSet<String>,
    locals: BTreeSet<String>,
    symbols: BTreeSet<String>,
    calls: Vec<Call>,
    error: Option<String>,
}

impl Profile {
    fn reject(&mut self, span: proc_macro2::Span, message: &str) {
        let start = span.start();
        self.error
            .get_or_insert_with(|| format!("{}:{}: {message}", start.line, start.column + 1));
    }

    fn reserved(&self, name: &str) -> bool {
        self.imports.contains(name)
            || self.functions.contains(name)
            || INTRINSICS.contains(&name)
            || CONSTRUCTORS.contains(&name)
            || TYPES.contains(&name)
            || VALUES.contains(&name)
            || name.starts_with("__")
    }
}

impl<'ast> Visit<'ast> for Profile {
    fn visit_path(&mut self, path: &'ast syn::Path) {
        if let Some(segment) = path.segments.first() {
            self.symbols.insert(segment.ident.to_string());
        }
        visit::visit_path(self, path);
    }

    fn visit_attribute(&mut self, attribute: &'ast syn::Attribute) {
        self.reject(
            attribute.span(),
            "attributes are outside the syscall source profile",
        );
    }

    fn visit_macro(&mut self, mac: &'ast syn::Macro) {
        self.reject(mac.span(), "macros are outside the syscall source profile");
    }

    fn visit_item(&mut self, item: &'ast Item) {
        self.reject(
            item.span(),
            "nested items are outside the syscall source profile",
        );
    }

    fn visit_type(&mut self, ty: &'ast Type) {
        let allowed = match ty {
            Type::Path(path) => {
                path.qself.is_none() && TYPES.contains(&path_name(&path.path).as_str())
            }
            Type::Reference(_)
            | Type::Array(_)
            | Type::Slice(_)
            | Type::Tuple(_)
            | Type::TraitObject(_) => true,
            _ => false,
        };
        if allowed {
            visit::visit_type(self, ty);
        } else {
            self.reject(ty.span(), "type is outside the syscall source profile");
        }
    }

    fn visit_trait_bound(&mut self, bound: &'ast syn::TraitBound) {
        if path_name(&bound.path) != "std::error::Error" || bound.lifetimes.is_some() {
            self.reject(bound.span(), "unsupported trait bound");
        }
    }

    fn visit_pat(&mut self, pat: &'ast Pat) {
        match pat {
            Pat::Ident(binding) => {
                let name = binding.ident.to_string();
                if name == "None"
                    && binding.by_ref.is_none()
                    && binding.mutability.is_none()
                    && binding.subpat.is_none()
                {
                    return;
                }
                if !identifier(&name) || self.reserved(&name) {
                    self.reject(binding.ident.span(), "invalid or reserved local name");
                }
                self.locals.insert(name);
            }
            Pat::Path(path) => {
                if path.qself.is_some() || !VALUES.contains(&path_name(&path.path).as_str()) {
                    self.reject(path.span(), "unsupported pattern path");
                }
            }
            Pat::TupleStruct(tuple) => {
                if tuple.qself.is_some() || !VALUES.contains(&path_name(&tuple.path).as_str()) {
                    self.reject(tuple.span(), "unsupported pattern constructor");
                }
            }
            Pat::Struct(record) => {
                if record.qself.is_some()
                    || ![
                        "SleepOutcome::Interrupted",
                        "ClockSleepOutcome::Interrupted",
                        "LsmQuery::BufferTooSmall",
                        "KeyReadOutcome::BufferTooSmall",
                        "WaitIdOutcome::Signaled",
                    ]
                    .contains(&path_name(&record.path).as_str())
                {
                    self.reject(record.span(), "unsupported structure pattern");
                }
            }
            Pat::Tuple(_) | Pat::Type(_) | Pat::Wild(_) | Pat::Lit(_) | Pat::Or(_) => {}
            _ => self.reject(pat.span(), "pattern is outside the syscall source profile"),
        }
        visit::visit_pat(self, pat);
    }

    fn visit_expr(&mut self, expr: &'ast Expr) {
        match expr {
            Expr::Call(call) => {
                let Expr::Path(path) = call.func.as_ref() else {
                    self.reject(call.span(), "only direct named calls are supported");
                    return;
                };
                let name = path_name(&path.path);
                if path.qself.is_some()
                    || path
                        .path
                        .segments
                        .iter()
                        .any(|segment| !segment.arguments.is_empty())
                {
                    self.reject(path.span(), "unsupported call path");
                } else if self.imports.contains(&name) {
                    let location = path.span().start();
                    self.calls.push(Call {
                        name: name.clone(),
                        line: location.line,
                        column: location.column + 1,
                    });
                } else if !self.functions.contains(&name)
                    && !INTRINSICS.contains(&name.as_str())
                    && !CONSTRUCTORS.contains(&name.as_str())
                {
                    self.reject(
                        path.span(),
                        "call is neither an imported syscall nor a supported operation",
                    );
                }
                self.visit_expr_path(path);
                for (index, argument) in call.args.iter().enumerate() {
                    if name == "rt_sigprocmask" && index == 1 && self.imports.contains(&name) {
                        if let Expr::Closure(closure) = argument {
                            if closure.lifetimes.is_some()
                                || closure.constness.is_some()
                                || closure.movability.is_some()
                                || closure.asyncness.is_some()
                                || closure.capture.is_some()
                                || closure.inputs.len() != 1
                                || !matches!(closure.output, syn::ReturnType::Default)
                            {
                                self.reject(
                                    closure.span(),
                                    "expected a one-argument signal-scope callback",
                                );
                            }
                            visit::visit_expr_closure(self, closure);
                            continue;
                        }
                    }
                    self.visit_expr(argument);
                }
                return;
            }
            Expr::MethodCall(call) => {
                if call.turbofish.is_some() || !METHODS.contains(&call.method.to_string().as_str())
                {
                    self.reject(call.span(), "method is outside the syscall source profile");
                }
            }
            Expr::Struct(record) => {
                if record.qself.is_some()
                    || ![
                        "OpenOptions",
                        "TimerSpec",
                        "EpollEvent",
                        "QueueOpen",
                        "QueueCreate",
                        "FileTimes",
                        "Rlimit",
                        "SemaphoreOperation",
                        "IntervalSettings",
                        "CacheStatRange",
                        "SendDatagram4",
                    ]
                    .contains(&path_name(&record.path).as_str())
                    || record.rest.is_some()
                {
                    self.reject(record.span(), "unsupported structure construction");
                }
            }
            Expr::Lit(literal) => {
                if !matches!(
                    literal.lit,
                    syn::Lit::Int(_)
                        | syn::Lit::Bool(_)
                        | syn::Lit::Str(_)
                        | syn::Lit::Byte(_)
                        | syn::Lit::ByteStr(_)
                        | syn::Lit::CStr(_)
                ) {
                    self.reject(
                        literal.span(),
                        "literal is outside the syscall source profile",
                    );
                }
            }
            Expr::Path(path) => {
                let name = path_name(&path.path);
                if path.qself.is_some()
                    || (!self.locals.contains(&name) && !VALUES.contains(&name.as_str()))
                {
                    self.reject(path.span(), "value is outside the syscall source profile");
                }
            }
            Expr::Array(_)
            | Expr::Assign(_)
            | Expr::Binary(_)
            | Expr::Block(_)
            | Expr::Break(_)
            | Expr::Cast(_)
            | Expr::Continue(_)
            | Expr::Field(_)
            | Expr::Group(_)
            | Expr::If(_)
            | Expr::Index(_)
            | Expr::Let(_)
            | Expr::Loop(_)
            | Expr::Match(_)
            | Expr::Paren(_)
            | Expr::Range(_)
            | Expr::Reference(_)
            | Expr::Repeat(_)
            | Expr::Return(_)
            | Expr::Try(_)
            | Expr::Tuple(_)
            | Expr::Unary(_)
            | Expr::While(_) => {}
            _ => self.reject(
                expr.span(),
                "expression is outside the syscall source profile",
            ),
        }
        visit::visit_expr(self, expr);
    }
}

pub fn parse(source: &str) -> Result<Module, String> {
    let mut imports = BTreeSet::new();
    let mut body = String::new();
    let mut leading = true;
    for (index, line) in source.lines().enumerate() {
        let text = line.trim();
        if leading && text.starts_with("import ") {
            let name = text
                .strip_prefix("import linux.syscalls.")
                .ok_or_else(|| format!("{}:1: expected import linux.syscalls.NAME", index + 1))?;
            if !identifier(name)
                || name.starts_with("__")
                || name == "main"
                || INTRINSICS.contains(&name)
                || CONSTRUCTORS.contains(&name)
                || TYPES.contains(&name)
                || VALUES.contains(&name)
                || !imports.insert(name.to_owned())
            {
                return Err(format!(
                    "{}:1: invalid or duplicate syscall import",
                    index + 1
                ));
            }
            body.push('\n');
            continue;
        }
        if !text.is_empty() && !text.starts_with("//") {
            leading = false;
        }
        body.push_str(line);
        body.push('\n');
    }
    if imports.is_empty() {
        return Err("expected at least one linux.syscalls import".into());
    }

    let file = syn::parse_file(&body).map_err(|error| {
        let location = error.span().start();
        format!("{}:{}: {error}", location.line, location.column + 1)
    })?;
    if file.shebang.is_some() || !file.attrs.is_empty() {
        return Err("file directives are outside the syscall source profile".into());
    }
    let mut functions = BTreeSet::new();
    for item in &file.items {
        let Item::Fn(function) = item else {
            return Err("only function definitions may follow the import section".into());
        };
        let name = function.sig.ident.to_string();
        let signature = &function.sig;
        if !identifier(&name)
            || name.starts_with("__")
            || imports.contains(&name)
            || INTRINSICS.contains(&name.as_str())
            || CONSTRUCTORS.contains(&name.as_str())
            || TYPES.contains(&name.as_str())
            || VALUES.contains(&name.as_str())
            || !functions.insert(name)
            || !matches!(function.vis, syn::Visibility::Inherited)
            || signature.unsafety.is_some()
            || signature.asyncness.is_some()
            || signature.abi.is_some()
            || signature.constness.is_some()
            || !signature.generics.params.is_empty()
            || signature.generics.where_clause.is_some()
            || signature.variadic.is_some()
        {
            return Err(format!("unsupported declaration for {}", signature.ident));
        }
    }
    if !functions.contains("main") {
        return Err("expected a main function".into());
    }
    let mut profile = Profile {
        imports: imports.clone(),
        functions,
        locals: BTreeSet::new(),
        symbols: BTreeSet::new(),
        calls: Vec::new(),
        error: None,
    };
    for item in &file.items {
        let Item::Fn(function) = item else {
            unreachable!()
        };
        profile.locals.clear();
        visit::visit_item_fn(&mut profile, function);
    }
    if let Some(error) = profile.error {
        return Err(error);
    }

    Ok(Module {
        imports,
        symbols: profile.symbols,
        body: file.into_token_stream().to_string(),
        calls: profile.calls,
    })
}

#[cfg(test)]
mod tests {
    use super::parse;

    #[test]
    fn retains_exact_import_calls_and_spans() {
        let module = parse(
            "import linux.syscalls.read\n\nfn main() { let _value = read(stdin_fd(), &mut [0_u8; 1]); }",
        )
        .unwrap();
        assert_eq!(module.imports.iter().next().unwrap(), "read");
        assert_eq!(module.calls.len(), 1);
        assert_eq!(module.calls[0].name, "read");
        assert_eq!((module.calls[0].line, module.calls[0].column), (3, 26));
    }

    #[test]
    fn admits_checked_callbacks_only_in_the_imported_signal_scope() {
        let imports = "import linux.syscalls.rt_sigprocmask\nimport linux.syscalls.signalfd4\n";
        let legal = "fn main() { rt_sigprocmask(UserSignals::USER1, |scope| signalfd4(scope)); }";
        let module = parse(&format!("{imports}{legal}")).unwrap();
        assert_eq!(module.calls.len(), 2);
        for body in [
            "fn main() { let callback = |scope| signalfd4(scope); }",
            "fn main() { rt_sigprocmask(UserSignals::USER1, |scope| include!(\"unsafe.rs\")); }",
            "fn main() { rt_sigprocmask(UserSignals::USER1, move |scope| signalfd4(scope)); }",
        ] {
            assert!(parse(&format!("{imports}{body}")).is_err(), "{body}");
        }
    }

    #[test]
    fn rejects_paths_that_bypass_import_resolution() {
        for body in [
            "fn main() { linux_syscalls_provider::read(stdin_fd(), &mut [0_u8; 1]); }",
            "fn main() { let x = read; }",
            "fn main() { let read = 0; }",
            "fn main() { unsafe { read(stdin_fd(), &mut [0_u8; 1]); } }",
            "fn main() { std::fs::read(\"name\"); }",
            "fn main() { include!(\"other.rs\"); }",
            "use std::fs; fn main() {}",
            "fn main() { let n = 1.5; n; }",
            "fn main() { let x = 0; let _ = &raw const x; }",
        ] {
            assert!(
                parse(&format!("import linux.syscalls.read\n{body}")).is_err(),
                "{body}"
            );
        }
    }
}
