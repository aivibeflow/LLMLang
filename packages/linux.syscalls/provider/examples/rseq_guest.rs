//! Exercise rseq after disabling the libc-managed registration in the probe.
use linux_syscalls_provider::{getcpu, getppid, rseq, rseq_unregister, EINVAL};
use std::{env, os::unix::process::CommandExt, process::Command};

const CHILD: &str = "LLMLANG_RSEQ_GUEST_CHILD";
const PROBE_ARG: &str = "--llmlang-disposable-guest-probe";

fn main() -> Result<(), Box<dyn std::error::Error>> {
    assert!(env::args().skip(1).eq([PROBE_ARG]));
    assert_eq!(getppid()?, 1, "run through the disposable guest init");
    if env::var_os(CHILD).is_none() {
        return Err(Command::new("/probe")
            .arg(PROBE_ARG)
            .env("GLIBC_TUNABLES", "glibc.pthread.rseq=0")
            .env(CHILD, "yes")
            .exec()
            .into());
    }

    let registration = rseq()?;
    assert_eq!(registration.cpu_id(), Some(getcpu()?.cpu));
    assert!(rseq().unwrap_err().is_errno(EINVAL));
    rseq_unregister(registration)?;
    drop(rseq()?);
    rseq_unregister(rseq()?)?;
    println!("LLMLANG_GUEST_CASE rseq_registers_observes_cpu_and_unregisters_on_own_thread");
    Ok(())
}
