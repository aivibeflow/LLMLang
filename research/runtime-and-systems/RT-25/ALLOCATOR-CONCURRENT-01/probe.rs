use std::alloc::System;
use std::path::Path;
use std::sync::mpsc::sync_channel;
use std::thread;
use std::time::{Duration, Instant};

#[global_allocator]
static ALLOCATOR: System = System;

mod bindings {
    #![allow(dead_code)]
    include!("../../PROTOTYPES/ALLOCATOR-COMPAT-01/probe.rs");

    pub fn check(expected: &std::path::Path) {
        let pinned = expected.canonicalize().unwrap();
        for symbol in [
            malloc as *const c_void,
            calloc as *const c_void,
            realloc as *const c_void,
            free as *const c_void,
            posix_memalign as *const c_void,
        ] {
            assert_eq!(std::fs::canonicalize(provider(symbol)).unwrap(), pinned);
        }
    }
}

const SIZES: [usize; 7] = [24, 96, 300, 1024, 4096, 32768, 65536];
const PER_PRODUCER: usize = 1024;
const CHUNK: usize = 4 * 1024 * 1024;

fn resident(field: &str) -> u64 {
    let status = std::fs::read_to_string("/proc/self/status").unwrap();
    status
        .lines()
        .find_map(|line| {
            let (key, value) = line.split_once(':')?;
            (key == field).then(|| value.split_whitespace().next().unwrap().parse().unwrap())
        })
        .unwrap()
}

fn size(producer: usize, ticket: usize) -> usize {
    SIZES[(producer + ticket) % SIZES.len()]
}

fn tag(producer: usize, ticket: usize) -> u8 {
    (producer * 31 + ticket * 13) as u8
}

fn churn(producers: usize) {
    let start = Instant::now();
    let (sender, receiver) = sync_channel(8);
    let mut workers = Vec::with_capacity(producers);
    for producer in 0..producers {
        let sender = sender.clone();
        workers.push(thread::spawn(move || {
            for ticket in 0..PER_PRODUCER {
                let length = size(producer, ticket);
                let value = tag(producer, ticket);
                let bytes = vec![value; length];
                sender.send((producer, ticket, bytes)).unwrap();
            }
        }));
    }
    drop(sender);
    let mut count = 0;
    let mut byte_count = 0;
    let mut checksum = 0u64;
    let mut seen = vec![false; producers * PER_PRODUCER];
    for (producer, ticket, bytes) in receiver {
        let position = producer * PER_PRODUCER + ticket;
        assert!(!seen[position]);
        seen[position] = true;
        let value = tag(producer, ticket);
        assert_eq!(bytes.len(), size(producer, ticket));
        assert!(bytes.iter().all(|byte| *byte == value));
        count += 1;
        byte_count += bytes.len();
        checksum += (position as u64 + 1) * (1 + bytes.len() as u64 + value as u64);
        drop(bytes);
    }
    for worker in workers {
        worker.join().unwrap();
    }
    assert!(seen.into_iter().all(|present| present));
    let elapsed = start.elapsed().as_nanos();
    let peak = resident("VmHWM");
    thread::sleep(Duration::from_millis(20));
    let after = resident("VmRSS");
    println!(
        "{{\"count\":{count},\"payload_bytes\":{byte_count},\"checksum\":{checksum},\"elapsed_ns\":{elapsed},\"peak_kib\":{peak},\"after_drop_kib\":{after}}}"
    );
}

fn address_limit() {
    let mut retained = Vec::with_capacity(96);
    for marker in 1..=96u8 {
        let mut bytes = Vec::new();
        if bytes.try_reserve_exact(CHUNK).is_err() {
            break;
        }
        bytes.resize(CHUNK, marker);
        retained.push(bytes);
    }
    let completed = retained.len();
    assert!(completed < 96, "expected address-space pressure");
    for (index, bytes) in retained.iter().enumerate() {
        let value = (index + 1) as u8;
        assert_eq!(bytes[0], value);
        assert_eq!(bytes[CHUNK - 1], value);
    }
    let peak = resident("VmHWM");
    drop(retained);
    let retry = Vec::<u8>::new().try_reserve_exact(CHUNK).is_ok();
    println!(
        "{{\"retained_chunks\":{completed},\"bytes_per_chunk\":{CHUNK},\"peak_kib\":{peak},\"retry_after_drop\":{retry}}}"
    );
}

fn main() {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    match args.as_slice() {
        [expected, mode, workers] if mode == "churn" => {
            bindings::check(Path::new(expected));
            churn(workers.parse().unwrap());
        }
        [expected, mode] if mode == "address-limit" => {
            bindings::check(Path::new(expected));
            address_limit();
        }
        _ => panic!("usage: probe EXPECTED_PROVIDER churn WORKERS | EXPECTED_PROVIDER address-limit"),
    }
}
