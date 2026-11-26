use linux_syscalls_provider::*;
use std::ffi::CString;
use std::os::fd::AsRawFd;

const CHILD_MODE: &str = "--llmlang-process-mrelease-child";

fn release_child(mut args: impl Iterator<Item = String>) -> Result<(), Box<dyn std::error::Error>> {
    unsafe extern "C" {
        #[link_name = "write"]
        fn libc_write(fd: i32, buffer: *const u8, len: usize) -> isize;
        #[link_name = "read"]
        fn libc_read(fd: i32, buffer: *mut u8, len: usize) -> isize;
    }
    let ready: i32 = args.next().unwrap().parse()?;
    let hold: i32 = args.next().unwrap().parse()?;
    assert!(args.next().is_none());
    let mut mapping = mmap(65536, Protection::ReadWrite)?;
    mapping.as_mut_slice().unwrap().fill(0x6d);
    assert_eq!(unsafe { libc_write(ready, b"R".as_ptr(), 1) }, 1);
    let mut byte = [0_u8];
    assert_eq!(unsafe { libc_read(hold, byte.as_mut_ptr(), 1) }, 1);
    assert_eq!(mapping.as_slice()[0], 0x6d);
    Ok(())
}

fn verify_mrelease() -> Result<(), Box<dyn std::error::Error>> {
    #[repr(C)]
    struct SchedulerParam {
        priority: i32,
    }
    unsafe extern "C" {
        #[link_name = "sched_setscheduler"]
        fn libc_sched_setscheduler(pid: i32, policy: i32, param: *const SchedulerParam) -> i32;
    }
    const SCHED_OTHER: i32 = 0;
    const SCHED_FIFO: i32 = 1;

    let (ready, ready_writer) = pipe()?;
    let (hold, _hold_writer) = pipe()?;
    let descriptors = [ready_writer.as_raw_fd(), hold.as_raw_fd()]
        .map(|fd| CString::new(fd.to_string()).unwrap());
    let image = ExecImage::new(
        c"/probe",
        &[
            c"probe",
            c"--llmlang-process-mrelease-child",
            descriptors[0].as_c_str(),
            descriptors[1].as_c_str(),
        ],
        &[],
    )?;
    let mut child = fork_execve(&image)?;
    let target = pidfd_open(&child)?;
    close(ready_writer)?;
    close(hold)?;
    let mut byte = [0_u8];
    assert_eq!(read(ready.borrow(), &mut byte)?, ReadOutcome::Progress(1));
    assert_eq!(byte, [b'R']);
    assert!(process_mrelease(&target).unwrap_err().is_errno(22));

    // The disposable guest has one CPU. Use a higher priority only for the
    // two nonblocking calls, so the signal commits group exit while the
    // ordinary-priority child still has its original address space.
    let priority = SchedulerParam { priority: 1 };
    if unsafe { libc_sched_setscheduler(0, SCHED_FIFO, &priority) } != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    let release =
        pidfd_send_signal(&target, ChildSignal::Terminate).and_then(|()| process_mrelease(&target));
    let ordinary = SchedulerParam { priority: 0 };
    if unsafe { libc_sched_setscheduler(0, SCHED_OTHER, &ordinary) } != 0 {
        return Err(std::io::Error::last_os_error().into());
    }

    let status = loop {
        match wait4(&mut child, 0) {
            Err(error) if error.is_errno(EINTR) => continue,
            result => break result?,
        }
    };
    assert_eq!(status.unwrap().signal(), Some(15));
    assert!(child.pid().is_none());
    release?;
    println!("LLMLANG_GUEST_CASE process_mrelease_guest_releases_exiting_tracked_child");
    assert!(process_mrelease(&target).unwrap_err().is_errno(3));
    println!("LLMLANG_GUEST_CASE process_mrelease_guest_preserves_running_and_reaped_errors");
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    match args.next().as_deref() {
        Some(CHILD_MODE) => return release_child(args),
        Some("--llmlang-disposable-guest-probe") => assert!(args.next().is_none()),
        _ => panic!("expected the disposable guest init"),
    }
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let mut mapping = mmap(4097, Protection::ReadWrite)?;
    let bytes = mapping.as_mut_slice().unwrap();
    bytes[0] = 0x41;
    bytes[4096] = 0x7a;
    assert_eq!(
        process_madvise(&mut mapping, ProcessAdvice::WillNeed)?,
        4097
    );
    assert_eq!(
        (mapping.as_slice()[0], mapping.as_slice()[4096]),
        (0x41, 0x7a)
    );
    println!("LLMLANG_GUEST_CASE process_madvise_guest_willneed_preserves_owned_bytes");

    mprotect(&mut mapping, Protection::ReadOnly)?;
    assert_eq!(process_madvise(&mut mapping, ProcessAdvice::Cold)?, 4097);
    assert_eq!(
        (mapping.as_slice()[0], mapping.as_slice()[4096]),
        (0x41, 0x7a)
    );
    assert!(mapping.as_mut_slice().is_none());
    println!("LLMLANG_GUEST_CASE process_madvise_guest_cold_preserves_readonly_mapping");
    munmap(mapping)?;
    verify_mrelease()
}
