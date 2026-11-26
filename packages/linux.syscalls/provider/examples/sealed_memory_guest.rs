use linux_syscalls_provider::*;
use std::{env, process::Command};

extern "C" {
    fn munmap(address: *const u8, length: usize) -> i32;
    fn raise(signal: i32) -> i32;
    fn waitpid(pid: i32, status: *mut i32, options: i32) -> i32;
    fn ptrace(request: u64, pid: i32, address: usize, data: usize) -> i64;
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    const MARKER: &str = "--llmlang-disposable-guest-probe";
    let args = env::args().skip(1).collect::<Vec<_>>();
    assert_eq!(args.first().map(String::as_str), Some(MARKER));
    if args.get(1).is_some_and(|arg| arg == "trace-me") {
        ptrace_trace_me()?;
        assert_eq!(unsafe { raise(19) }, 0);
        return Ok(());
    }
    assert_eq!(args.len(), 1);
    assert_eq!(getppid()?, 1, "run through the disposable guest init");
    let faults = userfaultfd()?;
    assert_eq!(fcntl_getfd(faults.borrow())? & 1, 1);
    assert_ne!(fcntl_getfl(faults.borrow())? & O_NONBLOCK, 0);
    close(faults)?;
    println!("LLMLANG_GUEST_CASE userfaultfd_creates_only_user_mode_descriptor");

    let secret = memfd_secret()?;
    assert_eq!(fcntl_getfd(secret.borrow())? & 1, 1);
    ftruncate(secret.borrow(), 4096)?;
    close(secret)?;
    println!("LLMLANG_GUEST_CASE memfd_secret_returns_owned_cloexec_file");

    let mut mapping = mmap(4096, Protection::ReadWrite)?;
    mapping.as_mut_slice().unwrap()[0] = 0x7a;
    let sealed = mseal(mapping)?;
    assert_eq!(sealed.as_slice()[0], 0x7a);
    let address = sealed.as_slice().as_ptr();
    assert_eq!(unsafe { munmap(address, 4096) }, -1);
    assert_eq!(std::io::Error::last_os_error().raw_os_error(), Some(1));
    assert_eq!(sealed.as_slice()[0], 0x7a);
    println!("LLMLANG_GUEST_CASE mseal_preserves_bytes_and_blocks_unmap");

    let mut tracee = Command::new("/probe").args([MARKER, "trace-me"]).spawn()?;
    let pid = tracee.id() as i32;
    let mut status = 0;
    assert_eq!(unsafe { waitpid(pid, &mut status, 0) }, pid);
    assert_eq!(status & 0xff, 0x7f);
    assert_eq!((status >> 8) & 0xff, 19);
    assert_eq!(unsafe { ptrace(7, pid, 0, 0) }, 0);
    assert!(tracee.wait()?.success());
    println!("LLMLANG_GUEST_CASE ptrace_traceme_voluntarily_stops_own_child");
    Ok(())
}
