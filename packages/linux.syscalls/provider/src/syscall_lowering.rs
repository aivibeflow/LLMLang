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

fn identifier(name: &str) -> bool {
    name.starts_with(|ch: char| ch.is_ascii_alphabetic() || ch == '_')
        && name
            .bytes()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == b'_')
}

fn pointer_type(kind: &str) -> bool {
    let Some((outer, inner)) = kind.split_once('<') else {
        return false;
    };
    matches!(outer, "ConstPtr" | "MutPtr")
        && inner
            .strip_suffix('>')
            .is_some_and(|inner| identifier(inner) || pointer_type(inner))
}

fn native_parameters(parameters: &str) -> Result<Vec<&str>, String> {
    if parameters.trim().is_empty() {
        return Ok(Vec::new());
    }
    let mut names = Vec::new();
    for parameter in parameters.split(',') {
        let (name, kind) = parameter
            .split_once(':')
            .ok_or("expected native parameter name and type")?;
        let (name, kind) = (name.trim(), kind.trim());
        if !identifier(name) || names.contains(&name) {
            return Err(format!("invalid or duplicate native parameter {name}"));
        }
        if !matches!(
            kind,
            "CString" | "U8" | "U16" | "U32" | "U64" | "Usize" | "I32" | "I64"
        ) && !pointer_type(kind)
        {
            return Err(format!("unsupported native parameter type {kind}"));
        }
        names.push(name);
    }
    if names.len() > 6 {
        return Err("native syscall takes at most six arguments".into());
    }
    Ok(names)
}

pub fn lower_native(source: &str) -> Result<String, String> {
    let (header, mut input) = source
        .split_once('\n')
        .ok_or("expected package linux.syscalls.native")?;
    if header
        .split_whitespace()
        .ne(["package", "linux.syscalls.native"])
    {
        return Err("expected package linux.syscalls.native".into());
    }
    let mut numbers = std::collections::BTreeMap::new();
    let mut used_numbers = BTreeSet::new();
    let mut wrappers = String::new();
    let mut dispatch = String::new();
    while !input.trim().is_empty() {
        let (signature, remaining) = input
            .split_once('{')
            .ok_or("expected native syscall body")?;
        let (body, remaining) = remaining
            .split_once('}')
            .ok_or("unclosed native syscall body")?;
        input = remaining;
        let (profile, signature) = signature
            .trim()
            .split_once(" fn ")
            .ok_or("expected native function")?;
        let (name, parameters) = signature
            .split_once('(')
            .ok_or("expected native parameters")?;
        let (parameters, result) = parameters
            .split_once(')')
            .ok_or("unclosed native parameters")?;
        let result = result
            .trim()
            .strip_prefix("->")
            .ok_or("expected native result type")?
            .trim();
        if !identifier(name) {
            return Err(format!("invalid native entry name {name}"));
        }
        let body = body
            .trim()
            .strip_prefix("syscall(")
            .ok_or("expected native syscall invocation")?;
        let (arguments, continuation) = body
            .split_once(')')
            .ok_or("unclosed native syscall invocation")?;
        let mut arguments = arguments.split(',').map(str::trim);
        let number = arguments
            .next()
            .and_then(|number| number.parse::<u16>().ok())
            .ok_or("expected native syscall number")?;
        if numbers.insert(name, number).is_some() || !used_numbers.insert(number) {
            return Err(format!("duplicate native entry {name} or number {number}"));
        }
        let parameters = native_parameters(parameters)?;
        if arguments.ne(parameters.iter().copied()) {
            return Err(format!(
                "{name}: syscall operands must match its declared parameter order"
            ));
        }
        match (profile, name, result, continuation.trim()) {
            ("unsafe", _, "AbiResult", "") => {
                if ["vfork", "rt_sigreturn", "uretprobe"].contains(&name) {
                    return Err(format!(
                        "{name}: requires its dedicated continuation profile"
                    ));
                }
                // The surrounding adapter provides the original register bits.
                // ABI lowering erases source types without creating Rust references
                // from pointers or narrowing the already-marshalled words.
                let mut lowered_words: [String; 6] = std::array::from_fn(|_| "0".into());
                let mut lowered_parameters = Vec::new();
                let mut routed_words = Vec::new();
                for (index, parameter) in parameters.iter().enumerate() {
                    let word = if parameter.starts_with('_') {
                        format!("arg_{index}_{}", parameter.trim_start_matches('_'))
                    } else {
                        format!("arg_{parameter}")
                    };
                    lowered_words[index] = word.clone();
                    lowered_parameters.push(format!("{word}: usize"));
                    routed_words.push(format!("words[{index}]"));
                }
                writeln!(
                    wrappers,
                    "#[inline]\nunsafe fn native_{name}({}) -> isize {{\n    unsafe {{ enter::<{number}>([{}]) }}\n}}",
                    lowered_parameters.join(", "),
                    lowered_words.join(", "),
                ).expect("writing to String");
                writeln!(
                    dispatch,
                    "        {number} => unsafe {{ native_{name}({}) }},",
                    routed_words.join(", ")
                )
                .expect("writing to String");
            }
            ("stackless", "vfork", "AbiResult", "")
            | ("restorer", "rt_sigreturn", "Never", "; trap()")
            | ("kernel", "uretprobe", "NativeContinuation", "")
                if parameters.is_empty() => {}
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
        r#"{wrappers}
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
