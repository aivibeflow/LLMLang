use linux_syscalls_provider::{
    capset_clear, getppid, prctl_set_no_new_privs, setdomainname, sethostname, setns_uts, uname,
    unshare_uts, unshare_uts_pinned, PinUtsError, SyscallError,
};
use std::env;
use std::process::Command;

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";
const EPERM: i32 = 1;

extern "C" {
    fn setuid(uid: u32) -> i32;
    fn prctl(option: i32, ...) -> i32;
}

fn case(name: &str) {
    println!("LLMLANG_GUEST_CASE {name}");
}

fn isolation() -> Result<(), SyscallError> {
    let initial = uname()?;
    let private = unshare_uts()?;
    assert_eq!(uname()?.node(), initial.node());

    sethostname(&private, b"llmlang-private-namespace")?;
    assert_eq!(uname()?.node().to_bytes(), b"llmlang-private-namespace");

    let maximum = [b'x'; 64];
    sethostname(&private, &maximum)?;
    assert_eq!(uname()?.node().to_bytes(), maximum);
    case("hostname_exact_64");

    let too_long = [b'x'; 65];
    assert!(matches!(
        sethostname(&private, &too_long),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(uname()?.node().to_bytes(), maximum);
    case("hostname_overlength_rejected");

    sethostname(&private, b"")?;
    assert!(uname()?.node().to_bytes().is_empty());
    case("hostname_empty");

    sethostname(&private, b"visible\0suffix")?;
    assert_eq!(uname()?.node().to_bytes(), b"visible");
    case("hostname_embedded_nul");

    setdomainname(&private, &maximum)?;
    assert_eq!(uname()?.domain().to_bytes(), maximum);
    assert!(matches!(
        setdomainname(&private, &too_long),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(uname()?.domain().to_bytes(), maximum);
    setdomainname(&private, b"local\0hidden")?;
    assert_eq!(uname()?.domain().to_bytes(), b"local");
    setdomainname(&private, b"")?;
    assert!(uname()?.domain().to_bytes().is_empty());
    case("domain_name_updates_only_private_namespace");
    Ok(())
}

fn permission_denial() -> Result<(), SyscallError> {
    let private = unshare_uts()?;
    let initial = uname()?;
    // The disposable guest uses its own kernel and process credentials.
    assert_eq!(unsafe { setuid(65534) }, 0);
    assert!(sethostname(&private, b"must-not-change")
        .unwrap_err()
        .is_errno(EPERM));
    assert_eq!(uname()?.node(), initial.node());
    case("hostname_permission_denied");
    assert!(setdomainname(&private, b"must-not-change")
        .unwrap_err()
        .is_errno(EPERM));
    assert_eq!(uname()?.domain(), initial.domain());
    case("domain_name_permission_denied");
    assert!(unshare_uts().unwrap_err().is_errno(EPERM));
    case("uts_permission_denied");
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut arguments = env::args().skip(1);
    assert_eq!(arguments.next().as_deref(), Some(GUEST_ARGUMENT));
    match arguments.next().as_deref() {
        Some("isolation") => isolation()?,
        Some("permission") => permission_denial()?,
        Some("setns") => namespace_rejoin()?,
        Some("capture-failure") => capture_failure()?,
        None => {
            assert_eq!(getppid()?, 1, "run through the disposable guest init");
            let initial = uname()?;
            for scenario in ["isolation", "permission", "setns", "capture-failure"] {
                let status = Command::new(env::current_exe().unwrap_or_else(|_| "/probe".into()))
                    .args([GUEST_ARGUMENT, scenario])
                    .status()?;
                assert!(status.success(), "guest scenario failed: {scenario}");
                assert_eq!(uname()?.node(), initial.node());
                assert_eq!(uname()?.domain(), initial.domain());
            }
            case("uts_inheritance_and_isolation");
        }
        Some(other) => panic!("unknown guest scenario {other}"),
    }
    Ok(())
}

fn namespace_rejoin() -> Result<(), Box<dyn std::error::Error>> {
    assert!(!std::path::Path::new("/proc/thread-self/ns/uts").exists());
    let (first, pinned_first) = unshare_uts_pinned()?;
    sethostname(&first, b"llmlang-owned-uts-one")?;
    setdomainname(&first, b"llmlang-owned-domain-one")?;
    let (second, pinned_second) = unshare_uts_pinned()?;
    sethostname(&second, b"llmlang-owned-uts-two")?;
    setdomainname(&second, b"llmlang-owned-domain-two")?;
    assert!(matches!(
        sethostname(&first, b"stale"),
        Err(SyscallError::InvalidInput(_))
    ));

    let rejoined = setns_uts(&pinned_first)?;
    let observed = uname()?;
    assert_eq!(observed.node().to_bytes(), b"llmlang-owned-uts-one");
    assert_eq!(observed.domain().to_bytes(), b"llmlang-owned-domain-one");
    assert!(matches!(
        setdomainname(&second, b"stale"),
        Err(SyscallError::InvalidInput(_))
    ));
    sethostname(&rejoined, b"llmlang-rejoined")?;
    assert_eq!(uname()?.node().to_bytes(), b"llmlang-rejoined");
    case("setns_rejoins_exact_owned_uts_and_invalidates_old_tokens");

    capset_clear()?;
    assert!(setns_uts(&pinned_second).unwrap_err().is_errno(EPERM));
    assert_eq!(uname()?.node().to_bytes(), b"llmlang-rejoined");
    assert!(sethostname(&rejoined, b"denied-in-kernel")
        .unwrap_err()
        .is_errno(EPERM));
    case("setns_permission_denial_preserves_current_uts_and_authority");
    Ok(())
}

#[repr(C)]
struct FilterInstruction {
    code: u16,
    jump_true: u8,
    jump_false: u8,
    value: u32,
}

#[repr(C)]
struct FilterProgram {
    count: u16,
    filters: *const FilterInstruction,
}

fn capture_failure() -> Result<(), Box<dyn std::error::Error>> {
    let former = unshare_uts()?;
    sethostname(&former, b"llmlang-before-capture")?;
    // Inject an errno for openat in this disposable child only.
    let instruction = |code, value, jump_false| FilterInstruction {
        code,
        jump_true: 0,
        jump_false,
        value,
    };
    let filters = [
        instruction(0x20, 4, 0),           // load architecture
        instruction(0x15, 0xc000_003e, 3), // x86-64
        instruction(0x20, 0, 0),           // load syscall number
        instruction(0x15, 257, 1),         // openat
        instruction(0x06, 0x0005_0018, 0), // EMFILE
        instruction(0x06, 0x7fff_0000, 0), // allow
    ];
    let program = FilterProgram {
        count: filters.len() as u16,
        filters: filters.as_ptr(),
    };
    prctl_set_no_new_privs()?;
    assert_eq!(
        unsafe {
            prctl(
                22,
                2_usize,
                &program as *const FilterProgram,
                0_usize,
                0_usize,
            )
        },
        0
    );
    let namespace = match unshare_uts_pinned() {
        Err(PinUtsError::Capture { namespace, error }) if error.is_errno(24) => namespace,
        other => panic!("expected a capture failure after entering new UTS: {other:?}"),
    };
    assert_eq!(uname()?.node().to_bytes(), b"llmlang-before-capture");
    assert!(matches!(
        sethostname(&former, b"stale"),
        Err(SyscallError::InvalidInput(_))
    ));
    sethostname(&namespace, b"llmlang-new-authority")?;
    assert_eq!(uname()?.node().to_bytes(), b"llmlang-new-authority");
    case("setns_capture_failure_returns_live_new_uts_authority");
    Ok(())
}
