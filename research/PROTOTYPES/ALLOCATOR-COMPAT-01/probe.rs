// Compare Rust's explicit System allocation boundary under two Linux providers.
use std::alloc::{GlobalAlloc, Layout, System};
use std::ffi::{c_char, c_int, c_void, CStr};
use std::ptr;
use std::thread;

#[repr(C)]
struct DlInfo {
    filename: *const c_char,
    base: *mut c_void,
    name: *const c_char,
    symbol: *mut c_void,
}

unsafe extern "C" {
    fn malloc(size: usize) -> *mut c_void;
    fn calloc(count: usize, size: usize) -> *mut c_void;
    fn realloc(memory: *mut c_void, size: usize) -> *mut c_void;
    fn free(memory: *mut c_void);
    fn posix_memalign(output: *mut *mut c_void, alignment: usize, size: usize) -> c_int;
    fn dladdr(address: *const c_void, info: *mut DlInfo) -> c_int;
}

fn provider(symbol: *const c_void) -> String {
    let mut details = DlInfo {
        filename: ptr::null(),
        base: ptr::null_mut(),
        name: ptr::null(),
        symbol: ptr::null_mut(),
    };
    // dladdr describes the process's bound symbol, rather than the installed libraries.
    unsafe {
        assert_ne!(dladdr(symbol, &mut details), 0);
        assert!(!details.filename.is_null());
        CStr::from_ptr(details.filename).to_string_lossy().into_owned()
    }
}

fn rust_round_trip(size: usize, alignment: usize, tag: u8) {
    let before = Layout::from_size_align(size, alignment).unwrap();
    let large = size * 3 + 1;
    let small = (size / 2).max(1);
    // A successful realloc retires the original pointer. Each later action uses the
    // new allocation with the corresponding size and the original alignment.
    unsafe {
        let first = System.alloc_zeroed(before);
        assert!(!first.is_null());
        assert_eq!(first as usize % alignment, 0);
        for i in 0..size {
            assert_eq!(first.add(i).read(), 0);
            first.add(i).write(tag.wrapping_add(i as u8));
        }

        let grown = System.realloc(first, before, large);
        assert!(!grown.is_null());
        assert_eq!(grown as usize % alignment, 0);
        for i in 0..size {
            assert_eq!(grown.add(i).read(), tag.wrapping_add(i as u8));
        }

        let smaller = System.realloc(grown, Layout::from_size_align(large, alignment).unwrap(), small);
        assert!(!smaller.is_null());
        assert_eq!(smaller as usize % alignment, 0);
        for i in 0..small {
            assert_eq!(smaller.add(i).read(), tag.wrapping_add(i as u8));
        }
        System.dealloc(smaller, Layout::from_size_align(small, alignment).unwrap());
    }
}

fn failed_c_resize_preserves_input() {
    // This request is intentionally impossible on the tested x86-64 providers.
    // The original 32-byte allocation remains owned after a null result.
    unsafe {
        let block = malloc(32);
        assert!(!block.is_null());
        ptr::write_bytes(block.cast::<u8>(), 0xA5, 32);
        let resized = realloc(block, usize::MAX);
        if !resized.is_null() {
            free(resized);
            panic!("impossible resize unexpectedly returned storage");
        }
        for i in 0..32 {
            assert_eq!(block.cast::<u8>().add(i).read(), 0xA5);
        }
        free(block);
    }
}

fn main() {
    let bound = provider(malloc as *const c_void);
    for symbol in [
        calloc as *const c_void, realloc as *const c_void,
        free as *const c_void, posix_memalign as *const c_void,
    ] {
        assert_eq!(provider(symbol), bound);
    }
    let expected = std::env::args().nth(1).expect("expected malloc provider filename");
    assert!(bound.contains(&expected), "bound provider {bound} does not match {expected}");
    let sizes = [1, 7, 8, 15, 31, 63, 127, 511, 4095, 4096];
    let alignments = [8, 16, 64, 256, 4096];
    let workers: Vec<_> = (0..4)
        .map(|worker| {
            thread::spawn(move || {
                for round in 0..16 {
                    for size in sizes {
                        for alignment in alignments {
                            rust_round_trip(size, alignment, (worker * 16 + round) as u8);
                        }
                    }
                }
            })
        })
        .collect();
    for worker in workers {
        worker.join().unwrap();
    }
    failed_c_resize_preserves_input();
    println!("{bound}: 3200 Rust allocation sequences and C resize-failure check passed");
}
