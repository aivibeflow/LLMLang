use linux_syscalls_provider::{
    fcntl_getfd, getpid, getppid, getsid, prctl_set_no_new_privs, read, vhangup_private_pty, write,
    PtyHangupError, ReadOutcome,
};
use std::os::fd::AsFd;
use std::process::Command;

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";

unsafe extern "C" {
    fn signal(number: i32, disposition: usize) -> usize;
    fn prctl(option: i32, ...) -> i32;
}

fn handle_hangup_signal() {
    const SIGHUP: i32 = 1;
    const SIG_IGN: usize = 1;
    const SIG_ERR: usize = usize::MAX;
    assert_ne!(unsafe { signal(SIGHUP, SIG_IGN) }, SIG_ERR);
}

fn hangup() -> Result<(), Box<dyn std::error::Error>> {
    handle_hangup_signal();
    let previous = getsid(0)?;
    let pty = vhangup_private_pty()?;
    assert_ne!(pty.session, previous);
    assert_eq!(pty.session, getsid(0)?);
    assert_eq!(pty.session, getpid()?);
    assert_eq!(fcntl_getfd(pty.master.as_fd())? & 1, 1);
    assert_eq!(fcntl_getfd(pty.slave.as_fd())? & 1, 1);
    assert_eq!(read(pty.slave.as_fd(), &mut [0; 1])?, ReadOutcome::Eof);
    assert!(write(pty.slave.as_fd(), b"x").unwrap_err().is_errno(5)); // EIO
    println!("LLMLANG_GUEST_CASE vhangup_revokes_live_owned_private_tty");
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

fn deny_hangup() -> Result<(), Box<dyn std::error::Error>> {
    handle_hangup_signal();
    let instruction = |code, value, jump_false| FilterInstruction {
        code,
        jump_true: 0,
        jump_false,
        value,
    };
    let filters = [
        instruction(0x20, 4, 0),           // load architecture
        instruction(0x15, 0xc000_003e, 3), // x86-64
        instruction(0x20, 0, 0),           // load syscall
        instruction(0x15, 153, 1),         // vhangup
        instruction(0x06, 0x0005_0001, 0), // EPERM
        instruction(0x06, 0x7fff_0000, 0), // allow others
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

    let pty = match vhangup_private_pty() {
        Err(PtyHangupError::Hangup { pty, error }) if error.is_errno(1) => pty,
        other => panic!("expected hangup denial with owned PTY: {other:?}"),
    };
    assert_eq!(pty.session, getsid(0)?);
    assert_eq!(write(pty.slave.as_fd(), b"x")?, 1);
    let mut sample = [0u8; 1];
    assert_eq!(
        read(pty.master.as_fd(), &mut sample)?,
        ReadOutcome::Progress(1)
    );
    assert_eq!(sample, *b"x");
    println!("LLMLANG_GUEST_CASE vhangup_errno_preserves_session_and_pty_endpoints");
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    assert_eq!(args.next().as_deref(), Some(GUEST_ARGUMENT));
    match args.next().as_deref() {
        Some("success") => hangup()?,
        Some("denial") => deny_hangup()?,
        None => {
            assert_eq!(getppid()?, 1, "run through the disposable guest init");
            let session = getsid(0)?;
            for scenario in ["success", "denial"] {
                let status = Command::new("/probe")
                    .args([GUEST_ARGUMENT, scenario])
                    .status()?;
                assert!(status.success(), "PTY guest scenario failed: {scenario}");
                assert_eq!(getsid(0)?, session);
            }
        }
        Some(value) => panic!("unknown PTY guest scenario: {value}"),
    }
    Ok(())
}
