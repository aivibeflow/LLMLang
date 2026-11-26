use linux_syscalls_provider::{getpid, getppid, uretprobe, UretprobeObservation};
use std::ffi::{c_char, c_int, c_ulong, c_void, CStr};
use std::fs;
use std::process::Command;

const GUEST_ARGUMENT: &str = "--llmlang-disposable-guest-probe";

unsafe extern "C" {
    fn mount(
        source: *const c_char,
        target: *const c_char,
        filesystem: *const c_char,
        flags: c_ulong,
        data: *const c_void,
    ) -> c_int;
    fn umount(target: *const c_char) -> c_int;
    fn setuid(uid: u32) -> c_int;
}

struct MountedGuestFs(&'static CStr);

impl MountedGuestFs {
    fn at(path: &'static CStr, filesystem: &CStr) -> std::io::Result<Self> {
        fs::create_dir(path.to_str().expect("fixed guest path"))?;
        // The guest owns the fresh mountpoint in its disposable root.
        let status = unsafe {
            mount(
                filesystem.as_ptr(),
                path.as_ptr(),
                filesystem.as_ptr(),
                0,
                std::ptr::null(),
            )
        };
        if status != 0 {
            return Err(std::io::Error::last_os_error());
        }
        Ok(Self(path))
    }
}

impl Drop for MountedGuestFs {
    fn drop(&mut self) {
        unsafe { umount(self.0.as_ptr()) };
    }
}

fn trace_fixed_return() -> Result<(), Box<dyn std::error::Error>> {
    const ENABLE: &str = "/trace/events/syscalls/sys_enter_uretprobe/enable";
    fs::write("/trace/tracing_on", "0")?;
    fs::write("/trace/trace", "\n")?;
    fs::write(ENABLE, "1")?;
    fs::write("/trace/tracing_on", "1")?;

    for (input, result) in [(0, 0x52a4_ccde), (u32::MAX, 0xad5b_3321)] {
        assert_eq!(
            uretprobe(input)?,
            UretprobeObservation { result, returns: 1 }
        );
    }

    fs::write("/trace/tracing_on", "0")?;
    fs::write(ENABLE, "0")?;
    let trace = fs::read_to_string("/trace/trace")?;
    let task = format!("-{}", getpid()?);
    let entries: Vec<_> = trace
        .lines()
        .filter(|line| line.contains(": sys_uretprobe()"))
        .collect();
    assert_eq!(entries.len(), 2, "{trace}");
    assert!(
        entries.iter().all(|line| {
            line.split_whitespace()
                .next()
                .is_some_and(|name| name.ends_with(&task))
        }),
        "{trace}"
    );
    println!("LLMLANG_GUEST_CASE uretprobe_kernel_trampoline_returns_exact_value");
    Ok(())
}

fn trace_unprivileged_return() -> Result<(), Box<dyn std::error::Error>> {
    const ENABLE: &str = "/trace/events/syscalls/sys_exit_perf_event_open/enable";
    fs::write("/trace/trace", "\n")?;
    fs::write(ENABLE, "1")?;
    fs::write("/trace/tracing_on", "1")?;
    let status = Command::new("/probe")
        .args([GUEST_ARGUMENT, "denied"])
        .status()?;
    fs::write("/trace/tracing_on", "0")?;
    fs::write(ENABLE, "0")?;
    assert!(status.success());
    let trace = fs::read_to_string("/trace/trace")?;
    let entries: Vec<_> = trace
        .lines()
        .filter(|line| line.contains(": sys_perf_event_open -> "))
        .collect();
    assert_eq!(entries.len(), 1, "{trace}");
    let raw = entries[0].split_once(" -> ").expect("perf result").1;
    let raw = u64::from_str_radix(raw.trim_start_matches("0x"), 16)? as i64;
    assert!(matches!(raw, -13 | -1), "{trace}");
    println!("LLMLANG_GUEST_CASE uretprobe_preserves_unprivileged_perf_denial");
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut arguments = std::env::args().skip(1);
    assert_eq!(arguments.next().as_deref(), Some(GUEST_ARGUMENT));
    if arguments.next().as_deref() == Some("denied") {
        assert_eq!(unsafe { setuid(65_534) }, 0);
        let error = uretprobe(17).unwrap_err();
        assert!(error.is_errno(13) || error.is_errno(1), "{error}");
        return Ok(());
    }
    assert_eq!(getppid()?, 1, "run through the disposable guest init");
    let _sys = MountedGuestFs::at(c"/sys", c"sysfs")?;
    let _proc = MountedGuestFs::at(c"/proc", c"proc")?;
    let _trace = MountedGuestFs::at(c"/trace", c"tracefs")?;
    trace_fixed_return()?;
    trace_unprivileged_return()?;
    Ok(())
}
