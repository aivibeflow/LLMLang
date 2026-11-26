use linux_syscalls_provider::{
    add_key, getppid, keyctl_join_session, keyctl_read, keyctl_unlink, request_key, KeyReadOutcome,
    SyscallError,
};
use std::ffi::{c_char, c_long};
use std::ptr;

extern "C" {
    fn syscall(number: c_long, ...) -> c_long;
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert_eq!(
        std::env::args().nth(1).as_deref(),
        Some("--llmlang-disposable-guest-probe")
    );
    assert_eq!(getppid()?, 1, "run through the disposable guest init");
    let mut ring = keyctl_join_session()?;
    assert!(matches!(
        keyctl_join_session(),
        Err(SyscallError::InvalidInput(_))
    ));
    println!("LLMLANG_GUEST_CASE keyring_creates_one_anonymous_session");

    for label in [c"unscoped", c"llmlang:", c"llmlang:bad/name"] {
        assert!(matches!(
            add_key(&mut ring, label, b"value"),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    for payload in [&[][..], &[0u8; 1025][..]] {
        assert!(matches!(
            add_key(&mut ring, c"llmlang:bad-payload", payload),
            Err(SyscallError::InvalidInput(_))
        ));
    }
    println!("LLMLANG_GUEST_CASE keyring_rejects_unscoped_key_input");

    {
        let payload = b"disposable\0guest value";
        let len = payload.len();
        let mut key = add_key(&mut ring, c"llmlang:guest-read", payload)?;
        request_key(&key)?;
        let mut small = [0xA5; 4];
        assert_eq!(
            keyctl_read(&key, &mut small)?,
            KeyReadOutcome::BufferTooSmall {
                required_bytes: len
            },
        );
        assert_eq!(small, [0xA5; 4]);
        assert_eq!(
            keyctl_read(&key, &mut [])?,
            KeyReadOutcome::BufferTooSmall {
                required_bytes: len
            },
        );
        let mut output = [0xA5; 32];
        assert_eq!(
            keyctl_read(&key, &mut output)?,
            KeyReadOutcome::Written(len)
        );
        assert_eq!(&output[..len], payload);
        assert!(output[len..].iter().all(|byte| *byte == 0xA5));
        println!("LLMLANG_GUEST_CASE keyring_queries_and_reads_exact_owned_value");

        keyctl_unlink(&mut key)?;
        assert!(matches!(
            request_key(&key),
            Err(SyscallError::InvalidInput(_))
        ));
        assert!(matches!(
            keyctl_read(&key, &mut output),
            Err(SyscallError::InvalidInput(_))
        ));
        assert!(matches!(
            keyctl_unlink(&mut key),
            Err(SyscallError::InvalidInput(_))
        ));
        println!("LLMLANG_GUEST_CASE keyring_unlink_consumes_owned_link");
    }

    let label = c"llmlang:guest-drop";
    drop(add_key(&mut ring, label, b"ephemeral scope")?);
    let lookup = unsafe {
        syscall(
            249,
            c"user".as_ptr(),
            label.as_ptr(),
            ptr::null::<c_char>(),
            0i32,
        )
    };
    assert_eq!(lookup, -1);
    assert_eq!(std::io::Error::last_os_error().raw_os_error(), Some(126));
    println!("LLMLANG_GUEST_CASE keyring_drop_removes_only_owned_link");
    Ok(())
}
