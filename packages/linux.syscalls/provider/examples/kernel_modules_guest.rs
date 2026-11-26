use linux_syscalls_provider::*;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(std::env::args()
        .skip(1)
        .eq(["--llmlang-disposable-guest-probe"]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");

    let bytes = std::fs::read("/loop.ko")?;
    let file = open(
        c"/loop.ko",
        OpenOptions {
            flags: O_RDONLY | O_CLOEXEC,
            mode: 0,
        },
    )?;
    let module = c"loop";
    assert!(delete_module(module).unwrap_err().is_errno(2));
    assert!(init_module(b"bad ELF").unwrap_err().is_errno(8));
    println!("LLMLANG_GUEST_CASE init_module_guest_rejects_short_image");

    init_module(&bytes)?;
    assert!(init_module(&bytes).unwrap_err().is_errno(17));
    println!("LLMLANG_GUEST_CASE init_module_guest_loads_signed_loop_and_reports_duplicate");
    delete_module(module)?;
    assert!(delete_module(module).unwrap_err().is_errno(2));

    assert_eq!(lseek(file.borrow(), 3, SeekOrigin::Start)?, 3);
    finit_module(file.borrow())?;
    assert_eq!(lseek(file.borrow(), 0, SeekOrigin::Current)?, 3);
    assert!(finit_module(file.borrow()).unwrap_err().is_errno(17));
    println!("LLMLANG_GUEST_CASE finit_module_guest_loads_signed_loop_and_preserves_offset");
    delete_module(module)?;
    assert!(delete_module(module).unwrap_err().is_errno(2));
    println!("LLMLANG_GUEST_CASE delete_module_guest_unloads_loop_and_reports_absence");

    let gid = GroupId::new(65534)?;
    let uid = UserId::new(65534)?;
    setresgid(Some(gid), Some(gid), Some(gid))?;
    setresuid(Some(uid), Some(uid), Some(uid))?;
    assert!(init_module(&bytes).unwrap_err().is_errno(1));
    assert!(finit_module(file.borrow()).unwrap_err().is_errno(1));
    assert!(delete_module(module).unwrap_err().is_errno(1));
    println!("LLMLANG_GUEST_CASE kernel_modules_guest_preserves_permission_errors");
    Ok(())
}
