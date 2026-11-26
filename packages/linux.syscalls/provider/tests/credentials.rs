use linux_syscalls_provider::*;

#[test]
fn current_credential_and_capability_observations_match_proc_status() {
    let status = std::fs::read_to_string("/proc/thread-self/status").unwrap();
    let field = |prefix: &str| {
        status
            .lines()
            .find_map(|line| line.strip_prefix(prefix))
            .unwrap()
            .trim()
    };
    let ids = |prefix| {
        field(prefix)
            .split_whitespace()
            .map(|value| value.parse::<u32>().unwrap())
            .collect::<Vec<_>>()
    };
    let assert_ids = |actual: CredentialIds, observed: &[u32]| {
        assert_eq!([actual.real, actual.effective, actual.saved], observed[..3]);
    };
    let uid = ids("Uid:");
    let gid = ids("Gid:");
    assert_ids(getresuid().unwrap(), &uid);
    assert_ids(getresgid().unwrap(), &gid);
    assert_eq!(setfsuid_query().unwrap(), uid[3]);
    assert_eq!(setfsgid_query().unwrap(), gid[3]);

    let observed = capget().unwrap();
    let hex = |prefix| u64::from_str_radix(field(prefix), 16).unwrap();
    assert_eq!(observed.effective, hex("CapEff:"));
    assert_eq!(observed.permitted, hex("CapPrm:"));
    assert_eq!(observed.inheritable, hex("CapInh:"));
    assert_eq!(observed, capget().unwrap());
}
