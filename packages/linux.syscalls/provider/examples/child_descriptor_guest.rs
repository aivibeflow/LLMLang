use linux_syscalls_provider::*;
use std::ffi::CString;
use std::os::fd::AsRawFd;

const CHILD_MODE: &str = "--llmlang-child-descriptor-probe";

fn child_branch(mut args: impl Iterator<Item = String>) {
    unsafe extern "C" {
        #[link_name = "dup2"]
        fn libc_dup2(old: i32, new: i32) -> i32;
        #[link_name = "read"]
        fn libc_read(fd: i32, buffer: *mut u8, len: usize) -> isize;
        #[link_name = "write"]
        fn libc_write(fd: i32, buffer: *const u8, len: usize) -> isize;
    }
    let replace = args.next().unwrap() == "replace";
    let expected: i32 = args.next().unwrap().parse().unwrap();
    let alternate: i32 = args.next().unwrap().parse().unwrap();
    let ready: i32 = args.next().unwrap().parse().unwrap();
    let release: i32 = args.next().unwrap().parse().unwrap();
    assert!(args.next().is_none());
    if replace {
        // Both numbers came from distinct descriptors inherited by this
        // isolated fixture. Deliberately change only the recorded slot.
        assert_eq!(unsafe { libc_dup2(alternate, expected) }, expected);
    }
    assert_eq!(unsafe { libc_write(ready, b"R".as_ptr(), 1) }, 1);
    let mut byte = [0_u8];
    assert_eq!(unsafe { libc_read(release, byte.as_mut_ptr(), 1) }, 1);
    assert_eq!(byte, [b'X']);
    std::process::exit(45);
}

fn wait_for_exit(child: &mut ChildPid) {
    loop {
        match wait4(child, 0) {
            Ok(Some(status)) => {
                assert_eq!(status.exited(), Some(45));
                break;
            }
            Err(error) if error.is_errno(EINTR) => continue,
            other => panic!("unexpected wait result: {other:?}"),
        }
    }
    assert!(child.pid().is_none());
}

fn exercise_recorded_slot(replace: bool) -> Result<(), Box<dyn std::error::Error>> {
    let (expected, expected_writer) = pipe()?;
    let (alternate, _alternate_writer) = pipe()?;
    let (ready, ready_writer) = pipe()?;
    let (release, release_writer) = pipe()?;
    let arguments: [CString; 4] = [
        expected.as_raw_fd(),
        alternate.as_raw_fd(),
        ready_writer.as_raw_fd(),
        release.as_raw_fd(),
    ]
    .map(|fd| CString::new(fd.to_string()).unwrap());
    let mode = if replace { c"replace" } else { c"inherit" };
    let image = ExecImage::new(
        c"/probe",
        &[
            c"probe",
            c"--llmlang-child-descriptor-probe",
            mode,
            arguments[0].as_c_str(),
            arguments[1].as_c_str(),
            arguments[2].as_c_str(),
            arguments[3].as_c_str(),
        ],
        &[],
    )?;
    let mut child = fork_execve(&image)?;
    let target = pidfd_open(&child)?;
    let known = KnownChildDescriptor::new(&target, expected.borrow());
    close(ready_writer)?;
    close(release)?;
    let mut signal = [0_u8];
    assert_eq!(read(ready.borrow(), &mut signal)?, ReadOutcome::Progress(1));
    assert_eq!(signal, [b'R']);

    let free = dup(expected.borrow())?;
    let vacant_number = free.as_raw_fd();
    close(free)?;
    let result = pidfd_getfd(&known);
    assert_eq!(write(release_writer.borrow(), b"X")?, 1);
    wait_for_exit(&mut child);

    if replace {
        assert_eq!(
            result.unwrap_err(),
            ChildDescriptorError::DifferentDescription
        );
        let free = dup(expected.borrow())?;
        assert_eq!(free.as_raw_fd(), vacant_number);
        println!(
            "LLMLANG_GUEST_CASE pidfd_getfd_guest_rejects_replaced_slot_and_discards_candidate"
        );
    } else {
        let copied = result?;
        assert_eq!(fcntl_getfd(copied.borrow())? & 1, 1);
        assert!(kcmp(expected.borrow(), copied.borrow())?);
        assert_eq!(write(expected_writer.borrow(), b"K")?, 1);
        assert_eq!(
            read(copied.borrow(), &mut signal)?,
            ReadOutcome::Progress(1)
        );
        assert_eq!(signal, [b'K']);
        assert!(matches!(
            pidfd_getfd(&known),
            Err(ChildDescriptorError::Duplicate(error)) if error.is_errno(3)
        ));
        println!(
            "LLMLANG_GUEST_CASE pidfd_getfd_guest_copies_known_inheritance_and_preserves_cloexec"
        );
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    match args.next().as_deref() {
        Some(CHILD_MODE) => child_branch(args),
        Some("--llmlang-disposable-guest-probe") => {
            assert!(args.next().is_none());
            assert_eq!(getppid()?, 1, "run through the disposable guest init");
        }
        _ => panic!("expected the disposable guest init"),
    }

    let (reader, writer) = pipe()?;
    let duplicate = dup(reader.borrow())?;
    assert!(kcmp(reader.borrow(), duplicate.borrow())?);
    assert!(!kcmp(reader.borrow(), writer.borrow())?);
    println!("LLMLANG_GUEST_CASE kcmp_guest_compares_only_own_open_file_descriptions");
    exercise_recorded_slot(false)?;
    exercise_recorded_slot(true)
}
