use linux_syscalls_provider::*;
use std::{env, fs, process::Command};

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";

extern "C" {
    fn mount(source: *const i8, target: *const i8, kind: *const i8, flags: u64, data: usize)
        -> i32;
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    assert_eq!(args.first().map(String::as_str), Some(GUEST_ARGUMENT));
    match args.get(1).map(String::as_str) {
        Some("accounting-child") => return Ok(()),
        Some("unprivileged-kexec") => {
            setuid(UserId::new(65534)?)?;
            assert!(kexec_load_unload().unwrap_err().is_errno(1));
            assert!(kexec_file_unload().unwrap_err().is_errno(1));
            return Ok(());
        }
        _ => {}
    }
    assert_eq!(args.len(), 1);
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let file = "/llmlang-acct-fixture";
    fs::File::create(file)?;
    acct(Some(c"/llmlang-acct-fixture"))?;
    let child = Command::new("/probe")
        .args([GUEST_ARGUMENT, "accounting-child"])
        .status();
    acct(None)?;
    assert!(child?.success());
    assert!(fs::metadata(file)?.len() > 0);
    fs::remove_file(file)?;
    println!("LLMLANG_GUEST_CASE accounting_records_exit_and_disables_cleanly");

    fs::create_dir("/llmlang-proc")?;
    let mounted = unsafe {
        mount(
            c"proc".as_ptr(),
            c"/llmlang-proc".as_ptr(),
            c"proc".as_ptr(),
            0,
            0,
        )
    };
    assert_eq!(mounted, 0);
    let policy = "/llmlang-proc/sys/kernel/ctrl-alt-del";
    let original = fs::read_to_string(policy)?;
    reboot_cad_control(true)?;
    assert_eq!(fs::read_to_string(policy)?.trim(), "1");
    reboot_cad_control(false)?;
    assert_eq!(fs::read_to_string(policy)?.trim(), "0");
    reboot_cad_control(original.trim() == "1")?;
    println!("LLMLANG_GUEST_CASE reboot_cad_flags_change_only_guest_policy");

    fs::create_dir("/llmlang-sys")?;
    let mounted = unsafe {
        mount(
            c"sysfs".as_ptr(),
            c"/llmlang-sys".as_ptr(),
            c"sysfs".as_ptr(),
            0,
            0,
        )
    };
    assert_eq!(mounted, 0);
    let staged = "/llmlang-sys/kernel/kexec_loaded";
    assert_eq!(fs::read_to_string(staged)?.trim(), "0");
    kexec_load_unload()?;
    assert_eq!(fs::read_to_string(staged)?.trim(), "0");
    kexec_file_unload()?;
    assert_eq!(fs::read_to_string(staged)?.trim(), "0");
    println!("LLMLANG_GUEST_CASE kexec_unload_native_entries_are_idempotent_for_empty_guest");

    let unprivileged = Command::new("/probe")
        .args([GUEST_ARGUMENT, "unprivileged-kexec"])
        .status()?;
    assert!(unprivileged.success());
    assert_eq!(fs::read_to_string(staged)?.trim(), "0");
    println!("LLMLANG_GUEST_CASE kexec_unload_denial_preserves_guest_staging_state");
    Ok(())
}
