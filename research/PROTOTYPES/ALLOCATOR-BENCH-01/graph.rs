// Allocation workload shaped like immutable declarations and a reverse-use index.
use std::collections::{HashMap, VecDeque};
use std::ffi::{c_char, c_int, c_void, CStr};
use std::fmt::Write;
use std::ptr;

#[repr(C)]
struct DlInfo {
    filename: *const c_char,
    base: *mut c_void,
    name: *const c_char,
    symbol: *mut c_void,
}

unsafe extern "C" {
    fn malloc(size: usize) -> *mut c_void;
    fn dladdr(address: *const c_void, info: *mut DlInfo) -> c_int;
}

fn check_provider(expected: &str) {
    let mut details = DlInfo {
        filename: ptr::null(),
        base: ptr::null_mut(),
        name: ptr::null(),
        symbol: ptr::null_mut(),
    };
    // Inspect the dynamically bound allocator before entering the timed phases.
    unsafe {
        assert_ne!(dladdr(malloc as *const c_void, &mut details), 0);
        assert!(!details.filename.is_null());
        let found = CStr::from_ptr(details.filename).to_string_lossy();
        assert!(found.ends_with(expected), "unexpected allocator {found}");
    }
}
use std::time::Instant;

fn memory_kib(field: &str) -> usize {
    let status = std::fs::read_to_string("/proc/self/status").unwrap();
    let (_, value) = status.lines()
        .find_map(|line| line.split_once(':').filter(|(key, _)| *key == field))
        .expect("required procfs memory field");
    value.split_whitespace().next().unwrap().parse().unwrap()
}

fn make_graph(size: usize) -> (HashMap<String, usize>, Vec<Vec<usize>>) {
    let mut names = HashMap::with_capacity(size);
    let mut incoming = vec![Vec::new(); size];
    for id in 0..size {
        names.insert(format!("workload.package.module{}.function_{id}", id % 997), id);
        for distance in [2, 7, 31, 127, 4093] {
            if let Some(dependency) = id.checked_sub(distance) {
                incoming[dependency].push(id);
            }
        }
    }
    (names, incoming)
}

fn impact(names: &HashMap<String, usize>, incoming: &[Vec<usize>]) -> u64 {
    let mut signature = 0u64;
    for module in [0, 43, 258, 913] {
        let root = names[&format!("workload.package.module{module}.function_{module}")];
        let mut pending = VecDeque::from([root]);
        let mut visited = vec![false; incoming.len()];
        visited[root] = true;
        let mut evidence = String::new();
        while let Some(id) = pending.pop_front() {
            writeln!(evidence, "{{\"affected\":{id}}}").unwrap();
            signature = signature.wrapping_mul(1099511628211).wrapping_add(id as u64);
            for caller in &incoming[id] {
                if !visited[*caller] {
                    visited[*caller] = true;
                    pending.push_back(*caller);
                }
            }
        }
        signature ^= evidence.len() as u64;
        std::hint::black_box(evidence);
    }
    signature
}

fn main() {
    check_provider(&std::env::args().nth(1).expect("allocator filename"));
    std::hint::black_box(make_graph(2048));
    let baseline = memory_kib("VmRSS");
    let start = Instant::now();
    let (names, incoming) = make_graph(200_000);
    let build_ns = start.elapsed().as_nanos();
    let live = memory_kib("VmRSS");
    let evaluate = Instant::now();
    let check = impact(&names, &incoming);
    let impact_ns = evaluate.elapsed().as_nanos();
    let peak = memory_kib("VmHWM");
    drop((names, incoming));
    std::thread::sleep(std::time::Duration::from_millis(50));
    let after_drop = memory_kib("VmRSS");
    println!(
        "{{\"build_ns\":{build_ns},\"impact_ns\":{impact_ns},\"baseline_kib\":{baseline},\
         \"live_kib\":{live},\"peak_kib\":{peak},\"after_drop_kib\":{after_drop},\"checksum\":\"{check:016x}\"}}"
    );
}
