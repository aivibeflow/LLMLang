use linux_syscalls_provider::*;

extern "C" {
    #[link_name = "getppid"]
    fn libc_getppid() -> i32;
    #[link_name = "getuid"]
    fn libc_getuid() -> u32;
    #[link_name = "getgid"]
    fn libc_getgid() -> u32;
    #[link_name = "geteuid"]
    fn libc_geteuid() -> u32;
    #[link_name = "getegid"]
    fn libc_getegid() -> u32;
}

#[test]
fn system_identity_and_metadata() {
    let uts = uname().unwrap();
    assert_eq!(uts.system().to_bytes(), b"Linux");
    assert_eq!(uts.machine().to_bytes(), b"x86_64");
    assert!(!uts.release().to_bytes().is_empty());
    let info = sysinfo().unwrap();
    assert!(info.uptime >= 0);
    assert!(info.memory_unit > 0);
    assert!(info.total_ram >= info.free_ram);

    assert_eq!(getpid().unwrap() as u32, std::process::id());
    // These libc queries independently observe the same process and credentials.
    assert_eq!(getppid().unwrap(), unsafe { libc_getppid() });
    assert_eq!(getuid().unwrap(), unsafe { libc_getuid() });
    assert_eq!(getgid().unwrap(), unsafe { libc_getgid() });
    assert_eq!(geteuid().unwrap(), unsafe { libc_geteuid() });
    assert_eq!(getegid().unwrap(), unsafe { libc_getegid() });
}

#[test]
fn random_reports_actual_progress() {
    assert_eq!(getrandom(&mut [], RandomMode::Blocking).unwrap(), 0);
    let mut bytes = [0_u8; 66];
    bytes[0] = 0xab;
    bytes[65] = 0xcd;
    let progress = getrandom(&mut bytes[1..65], RandomMode::Blocking).unwrap();
    assert!((1..=64).contains(&progress));
    assert_eq!(bytes[0], 0xab);
    assert_eq!(bytes[65], 0xcd);
    assert!(bytes[progress + 1..65].iter().all(|&byte| byte == 0));
}
