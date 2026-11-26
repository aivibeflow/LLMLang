use linux_syscalls_provider::{
    getppid, mmap, munmap, pkey_alloc, pkey_free, pkey_mprotect, prctl_set_no_new_privs, Protection,
};

use std::ffi::c_long;

#[repr(C)]
struct FilterInstruction {
    code: u16,
    jump_true: u8,
    jump_false: u8,
    value: u32,
}

#[repr(C)]
struct FilterProgram {
    len: u16,
    filters: *const FilterInstruction,
}

unsafe extern "C" {
    fn syscall(number: c_long, ...) -> c_long;
}

fn deny_key_release_in_this_thread() {
    prctl_set_no_new_privs().unwrap();
    let filters = [
        // Load seccomp_data.nr, then deny pkey_free without changing other calls.
        FilterInstruction {
            code: 0x20,
            jump_true: 0,
            jump_false: 0,
            value: 0,
        },
        FilterInstruction {
            code: 0x15,
            jump_true: 0,
            jump_false: 1,
            value: 331,
        },
        FilterInstruction {
            code: 0x06,
            jump_true: 0,
            jump_false: 0,
            value: 0x0005_0001,
        },
        FilterInstruction {
            code: 0x06,
            jump_true: 0,
            jump_false: 0,
            value: 0x7fff_0000,
        },
    ];
    let program = FilterProgram {
        len: filters.len() as u16,
        filters: filters.as_ptr(),
    };
    // SECCOMP_SET_MODE_FILTER with no TSYNC flag affects only this worker.
    assert_eq!(
        unsafe { syscall(317, 1_u32, 0_u32, &program as *const FilterProgram) },
        0
    );
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let mut keys = vec![pkey_alloc()?];
    for _ in 1..15 {
        match pkey_alloc() {
            Ok(key) => keys.push(key),
            Err(error) if error.is_errno(28) => break,
            Err(error) => return Err(error.into()),
        }
    }
    assert!(pkey_alloc().unwrap_err().is_errno(28));
    println!("LLMLANG_GUEST_CASE pkey_alloc_has_finite_owned_capacity");

    pkey_free(keys.pop().unwrap())?;
    drop(pkey_alloc()?);
    pkey_free(pkey_alloc()?)?;
    for key in keys {
        pkey_free(key)?;
    }
    println!("LLMLANG_GUEST_CASE pkey_free_explicit_and_drop_restore_capacity");

    let key = pkey_alloc()?;
    let key = std::thread::spawn(move || {
        deny_key_release_in_this_thread();
        let (error, key) = pkey_free(key).unwrap_err().into_parts();
        assert!(error.is_errno(1));
        key
    })
    .join()
    .unwrap();
    pkey_free(key)?;
    println!("LLMLANG_GUEST_CASE pkey_free_denial_returns_owned_key_for_retry");

    let mut mapping = mmap(4097, Protection::ReadWrite)?;
    let base = mapping.as_slice().as_ptr();
    mapping.as_mut_slice().unwrap()[4096] = 0xa5;
    pkey_mprotect(&mut mapping, Protection::ReadOnly)?;
    assert_eq!(mapping.as_slice().as_ptr(), base);
    assert_eq!(mapping.as_slice().len(), 4097);
    assert_eq!(mapping.as_slice()[4096], 0xa5);
    assert!(mapping.as_mut_slice().is_none());
    pkey_mprotect(&mut mapping, Protection::ReadWrite)?;
    mapping.as_mut_slice().unwrap()[0] = 0x5a;
    assert_eq!(
        (mapping.as_slice()[0], mapping.as_slice()[4096]),
        (0x5a, 0xa5)
    );
    munmap(mapping)?;
    println!("LLMLANG_GUEST_CASE pkey_mprotect_default_key_preserves_mapping");
    Ok(())
}
