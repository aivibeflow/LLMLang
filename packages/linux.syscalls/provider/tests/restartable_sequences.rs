use linux_syscalls_provider::{rseq, rseq_unregister, EINVAL};
use std::{env, process::Command};

const CHILD: &str = "LLMLANG_RSEQ_TEST_CHILD";
const CASE: &str = "rseq_registers_observes_cpu_and_unregisters_on_own_thread";

#[test]
fn rseq_registers_observes_cpu_and_unregisters_on_own_thread() {
    if env::var_os(CHILD).is_none() {
        let status = Command::new(env::current_exe().unwrap())
            .args(["--exact", CASE, "--nocapture"])
            .env("GLIBC_TUNABLES", "glibc.pthread.rseq=0")
            .env(CHILD, "yes")
            .status()
            .unwrap();
        assert!(status.success());
        return;
    }

    let registration = rseq().unwrap();
    assert!(registration.cpu_id().is_some());
    assert!(rseq().unwrap_err().is_errno(EINVAL));
    rseq_unregister(registration).unwrap();

    drop(rseq().unwrap());
    rseq_unregister(rseq().unwrap()).unwrap();
}
