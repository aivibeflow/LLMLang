//! Lowers the LLMLang provider profile to the native Linux x86-64 ABI.
use std::collections::BTreeSet;
use std::fmt::Write;

#[derive(Clone, Copy)]
enum Operand {
    Directory,
    Path,
    Flags,
    Mode,
}

impl Operand {
    fn lower(self, source: &str) -> Option<&'static str> {
        match (
            self,
            source.split_whitespace().collect::<Vec<_>>().as_slice(),
        ) {
            (Self::Directory, ["directory"]) => Some("directory.argument()"),
            (Self::Path, ["path"]) => Some("path.as_ptr() as usize"),
            (Self::Flags, ["options.flags"]) => Some("options.flags as usize"),
            (Self::Mode, ["options.mode"]) => Some("options.mode as usize"),
            _ => None,
        }
    }
}

struct Syscall {
    name: &'static str,
    signature: &'static str,
    parameters: &'static str,
    constant: &'static str,
    operands: &'static [Operand],
}

use Operand::{Directory, Flags, Mode, Path};

const CALLS: &[Syscall] = &[
    Syscall {
        name: "open",
        signature: "pub fn open(path: CString, options: OpenOptions) -> OpenResult",
        parameters: "path: &CStr, options: OpenOptions",
        constant: "abi::OPEN",
        operands: &[Path, Flags, Mode],
    },
    Syscall {
        name: "openat",
        signature:
            "pub fn openat(directory: Directory, path: CString, options: OpenOptions) -> OpenResult",
        parameters: "directory: Directory<'_>, path: &CStr, options: OpenOptions",
        constant: "abi::OPENAT",
        operands: &[Directory, Path, Flags, Mode],
    },
];

pub fn lower(source: &str) -> Result<String, String> {
    let (header, mut input) = source
        .split_once('\n')
        .ok_or("expected package linux.syscalls")?;
    if header.split_whitespace().ne(["package", "linux.syscalls"]) {
        return Err("expected package linux.syscalls".into());
    }

    let mut emitted = BTreeSet::new();
    let mut rust = String::new();
    while !input.trim().is_empty() {
        let (signature, rest) = input.split_once('{').ok_or("expected function body")?;
        let (body, rest) = rest.split_once('}').ok_or("unclosed function body")?;
        input = rest;
        let invocation = body
            .trim()
            .strip_prefix("syscall(")
            .and_then(|body| body.strip_suffix(')'))
            .ok_or("expected syscall(name, arguments...)")?;
        let mut arguments = invocation.split(',').map(str::trim);
        let name = arguments.next().expect("split always yields one field");
        let call = CALLS
            .iter()
            .find(|call| call.name == name)
            .ok_or_else(|| format!("unsupported native syscall {name}"))?;
        if signature
            .split_whitespace()
            .ne(call.signature.split_whitespace())
        {
            return Err(format!(
                "{name}: syscall does not match the function signature"
            ));
        }
        if !emitted.insert(call.name) {
            return Err(format!("{name}: duplicate implementation"));
        }

        let mut words = ["0"; 6];
        for (word, operand) in words.iter_mut().zip(call.operands) {
            *word = arguments
                .next()
                .and_then(|argument| operand.lower(argument))
                .ok_or_else(|| format!("{name}: invalid syscall operand"))?;
        }
        if arguments.next().is_some() {
            return Err(format!("{name}: too many syscall operands"));
        }
        let (name, parameters, entry) = (call.name, call.parameters, call.constant);
        writeln!(
            rust,
            "pub fn {name}({parameters}) -> Result<LinuxFd, SyscallError> {{
    let raw = unsafe {{ abi::invoke({entry}, [{}]) }};
    LinuxFd::from_result(raw)
}}",
            words.join(", ")
        )
        .expect("writing to String");
    }
    if emitted.len() != CALLS.len() {
        return Err("missing native syscall implementation".into());
    }
    Ok(rust)
}

pub fn lower_native(source: &str) -> Result<String, String> {
    let mut lines = source.lines();
    if lines
        .next()
        .map(str::split_whitespace)
        .is_none_or(|header| header.ne(["package", "linux.syscalls.native"]))
    {
        return Err("expected package linux.syscalls.native".into());
    }
    let mut numbers = std::collections::BTreeMap::new();
    let mut used_numbers = BTreeSet::new();
    let mut dispatch = String::new();
    for line in lines.map(str::trim).filter(|line| !line.is_empty()) {
        let (signature, body) = line
            .split_once(" { ")
            .ok_or("expected native syscall body")?;
        let body = body
            .strip_suffix(" }")
            .ok_or("unclosed native syscall body")?;
        let (profile, signature) = signature
            .split_once(" fn ")
            .ok_or("expected native function")?;
        let (name, parameters) = signature
            .split_once('(')
            .ok_or("expected native parameters")?;
        if !name.starts_with(|ch: char| ch.is_ascii_lowercase())
            || !name
                .bytes()
                .all(|ch| ch.is_ascii_lowercase() || ch.is_ascii_digit() || ch == b'_')
        {
            return Err(format!("invalid native entry name {name}"));
        }
        let number = body
            .split_once("syscall(")
            .and_then(|(_, args)| args.split([',', ')']).next())
            .and_then(|number| number.parse::<u16>().ok())
            .ok_or("expected native syscall number")?;
        if numbers.insert(name, number).is_some() || !used_numbers.insert(number) {
            return Err(format!("duplicate native entry {name} or number {number}"));
        }

        match (profile, name, parameters) {
            ("unsafe", _, "words: AbiWords) -> AbiResult")
                if body == format!("syscall({number}, words)") =>
            {
                if ["vfork", "rt_sigreturn", "uretprobe"].contains(&name) {
                    return Err(format!("{name}: requires its dedicated continuation profile"));
                }
                writeln!(dispatch, "        {number} => unsafe {{ enter::<{number}>(words) }},")
                    .expect("writing to String");
            }
            ("stackless", "vfork", "image: ExecWords) -> AbiResult")
                if body == format!("let child = syscall({number}); if child == 0 {{ syscall(execve, image); syscall(exit, 127); trap() }} child") => {}
            ("restorer", "rt_sigreturn", ") -> Never")
                if body == format!("syscall({number}); trap()") => {}
            ("kernel", "uretprobe", ") -> NativeContinuation")
                if body == format!("syscall({number})") => {}
            _ => return Err(format!("{name}: invalid native syscall signature or body")),
        }
    }
    let get = |name| {
        numbers
            .get(name)
            .copied()
            .ok_or_else(|| format!("missing native entry {name}"))
    };
    let (vfork, execve, exit, restorer) = (
        get("vfork")?,
        get("execve")?,
        get("exit")?,
        get("rt_sigreturn")?,
    );
    get("uretprobe")?;
    let code = format!(
        r#"
/// Invoke a declared native entry with already marshalled ABI words.
/// The caller is responsible for the validity and lifetime of indirect inputs.
#[inline]
pub(super) unsafe fn invoke(number: usize, words: [usize; 6]) -> isize {{
    match number {{
{dispatch}        _ => -(super::ENOSYS as isize),
    }}
}}

pub(super) const VFORK: usize = {vfork};
pub(super) const RT_SIGRETURN: usize = {restorer};

/// The child has no stack access while its address space is shared.
pub(super) unsafe fn vfork_exec(arguments: [usize; 6]) -> isize {{
    let raw: isize;
    unsafe {{
        asm!(
            "syscall",
            "test rax, rax",
            "jnz 2f",
            "mov eax, {{execve}}",
            "syscall",
            "mov edi, 127",
            "mov eax, {{exit}}",
            "syscall",
            "ud2",
            "2:",
            execve = const {execve}_usize,
            exit = const {exit}_usize,
            inlateout("rax") VFORK as isize => raw,
            inlateout("rdi") arguments[0] => _,
            in("rsi") arguments[1],
            in("rdx") arguments[2],
            lateout("rcx") _,
            lateout("r11") _,
            options(nostack),
        );
    }}
    raw
}}

// This symbol is installed only as a signal restorer. It has no callable
// package interface and enters using the kernel's own signal frame.
std::arch::global_asm!(
    ".pushsection .text.llmlang_fixed_signal_restorer,\"ax\",@progbits",
    ".p2align 4",
    ".global llmlang_fixed_signal_restorer",
    ".hidden llmlang_fixed_signal_restorer",
    ".type llmlang_fixed_signal_restorer,@function",
    "llmlang_fixed_signal_restorer:",
    "mov eax, {{operation}}",
    "syscall",
    "ud2",
    ".size llmlang_fixed_signal_restorer, .-llmlang_fixed_signal_restorer",
    ".popsection",
    operation = const RT_SIGRETURN,
);

unsafe extern "C" {{
    pub(super) fn llmlang_fixed_signal_restorer();
}}
"#
    );
    Ok(code)
}
