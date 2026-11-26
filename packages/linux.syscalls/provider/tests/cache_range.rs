use linux_syscalls_provider::*;
use std::os::fd::AsRawFd;
use std::process::Command;

#[test]
fn close_range_cloexec_marks_only_owned_fixture_slots_without_closing() {
    const CHILD: &str = "LLMLANG_CLOSE_RANGE_CLOEXEC_CHILD";
    if std::env::var_os(CHILD).is_none() {
        let output = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "close_range_cloexec_marks_only_owned_fixture_slots_without_closing",
            ])
            .env(CHILD, "1")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stdout)
        );
        return;
    }

    let (reader, writer) = pipe2(0).unwrap();
    let mut slots = [
        dup(reader.borrow()).unwrap(),
        dup(reader.borrow()).unwrap(),
        dup(reader.borrow()).unwrap(),
    ];
    slots.sort_by_key(AsRawFd::as_raw_fd);
    let numbers = slots.each_ref().map(|slot| slot.as_raw_fd() as u32);
    let flags = || {
        slots
            .each_ref()
            .map(|slot| fcntl_getfd(slot.borrow()).unwrap() & 1)
    };

    assert_eq!(flags(), [0; 3]);
    assert!(matches!(
        close_range_cloexec(numbers[2], numbers[0]),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(flags(), [0; 3]);
    close_range_cloexec(numbers[0], numbers[1]).unwrap();
    assert_eq!(flags(), [1, 1, 0]);

    assert_eq!(write(writer.borrow(), b"abc").unwrap(), 3);
    for (slot, expected) in slots.iter().zip(b"abc") {
        let mut byte = [0u8];
        assert_eq!(
            read(slot.borrow(), &mut byte).unwrap(),
            ReadOutcome::Progress(1)
        );
        assert_eq!(byte[0], *expected);
    }

    let [first, hole, last] = slots;
    close(hole).unwrap();
    close_range_cloexec(numbers[0], numbers[2]).unwrap();
    assert_eq!(fcntl_getfd(first.borrow()).unwrap() & 1, 1);
    assert_eq!(fcntl_getfd(last.borrow()).unwrap() & 1, 1);
}

#[test]
fn cachestat_reports_real_page_counts_without_changing_file_offset() {
    let file = memfd_create(c"llmlang-cachestat").unwrap();
    let pages = [0xf7; 12288];
    assert_eq!(write(file.borrow(), &pages).unwrap(), pages.len());
    assert_eq!(lseek(file.borrow(), 123, SeekOrigin::Start).unwrap(), 123);

    let query = |offset, length| cachestat(file.borrow(), CacheStatRange { offset, length });
    assert_eq!(query(4095, 1).unwrap().cached, 1);
    assert_eq!(query(4095, 2).unwrap().cached, 2);
    assert_eq!(query(4096, 0).unwrap().cached, 2);
    assert_eq!(query(12288, 4096).unwrap(), CacheStat::default());
    assert!(matches!(
        query(u64::MAX, 2),
        Err(SyscallError::InvalidInput(_))
    ));
    assert_eq!(lseek(file.borrow(), 0, SeekOrigin::Current).unwrap(), 123);
}
