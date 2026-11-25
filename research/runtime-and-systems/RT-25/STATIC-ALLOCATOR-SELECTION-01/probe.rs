use std::alloc::{alloc_zeroed, dealloc, realloc, Layout};
#[cfg(named_rust)]
use std::alloc::GlobalAlloc;
use std::ffi::c_void;
use std::slice;

extern "C" {
    #[cfg(named_rust)]
    fn mi_malloc_aligned(size: usize, alignment: usize) -> *mut u8;
    #[cfg(named_rust)]
    fn mi_realloc_aligned(pointer: *mut u8, size: usize, alignment: usize) -> *mut u8;
    #[cfg(named_rust)]
    fn mi_free(pointer: *mut u8);
    fn mi_heap_new() -> *mut c_void;
    fn mi_heap_delete(heap: *mut c_void);
    fn mi_heap_malloc_aligned(heap: *mut c_void, size: usize, align: usize) -> *mut u8;
    fn mi_heap_realloc_aligned(
        heap: *mut c_void,
        address: *mut u8,
        size: usize,
        align: usize,
    ) -> *mut u8;
    fn heap_owned_by(heap: *mut c_void, pointer: *const u8) -> i32;
    fn try_heap_release(heap: *mut c_void, pointer: *mut u8) -> i32;
    fn public_malloc_from_executable() -> i32;
    fn mimalloc_region(pointer: *const u8) -> i32;
    fn libc_allocate(size: usize, alignment: usize) -> *mut u8;
    fn libc_dispose(pointer: *mut u8);
}

#[cfg(named_rust)]
struct StaticMi;

#[cfg(named_rust)]
unsafe impl GlobalAlloc for StaticMi {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        mi_malloc_aligned(layout.size(), layout.align())
    }

    unsafe fn realloc(&self, pointer: *mut u8, layout: Layout, size: usize) -> *mut u8 {
        mi_realloc_aligned(pointer, size, layout.align())
    }

    unsafe fn dealloc(&self, pointer: *mut u8, _: Layout) {
        mi_free(pointer)
    }
}

#[cfg(named_rust)]
#[global_allocator]
static GLOBAL: StaticMi = StaticMi;

fn write_check(pointer: *mut u8, size: usize, alignment: usize, salt: usize) -> u64 {
    assert!(!pointer.is_null());
    assert_eq!((pointer as usize) % alignment, 0, "size={size} alignment={alignment} salt={salt}");
    let bytes = unsafe { slice::from_raw_parts_mut(pointer, size) };
    for (index, value) in bytes.iter_mut().enumerate() {
        *value = (index * 59 + salt) as u8;
    }
    checksum(bytes)
}

fn checksum(bytes: &[u8]) -> u64 {
    bytes.iter().enumerate().map(|(index, value)| (index as u64 + 1) * u64::from(*value)).sum()
}

fn main() {
    // The only component allocator use is on its creating thread, through explicit heap calls.
    unsafe {
        let first = mi_heap_new();
        let second = mi_heap_new();
        assert!(!first.is_null() && !second.is_null() && first != second);
        println!("public-malloc {}", public_malloc_from_executable());
        for alignment in [8, 16, 64, 128, 256, 4096] {
            for size in [1, 7, 31, 128, 1024, 4096] {
                let layout = Layout::from_size_align(size, alignment).unwrap();
                let rust_pointer = alloc_zeroed(layout);
                assert!(!rust_pointer.is_null());
                assert!(slice::from_raw_parts(rust_pointer, size).iter().all(|&byte| byte == 0));
                let wanted = write_check(rust_pointer, size, alignment, 3);
                let rust_new = realloc(rust_pointer, layout, size + 33);
                assert!(!rust_new.is_null() && (rust_new as usize) % alignment == 0);
                assert_eq!(checksum(slice::from_raw_parts(rust_new, size)), wanted);
                let rust_region = mimalloc_region(rust_new);
                dealloc(rust_new, Layout::from_size_align(size + 33, alignment).unwrap());

                let system = libc_allocate(size, alignment);
                let system_sum = write_check(system, size, alignment, 7);
                let c_region = mimalloc_region(system);
                libc_dispose(system);

                let block = mi_heap_malloc_aligned(first, size, alignment);
                let component_sum = write_check(block, size, alignment, 11);
                assert_eq!(heap_owned_by(first, block), 1);
                let wrong = try_heap_release(second, block);
                assert_eq!(wrong, 0);
                let enlarged = mi_heap_realloc_aligned(first, block, size + 33, alignment);
                assert!(!enlarged.is_null() && (enlarged as usize) % alignment == 0);
                assert_eq!(checksum(slice::from_raw_parts(enlarged, size)), component_sum);
                assert_eq!(heap_owned_by(first, enlarged), 1);
                assert_eq!(mimalloc_region(enlarged), 1);
                assert_eq!(try_heap_release(first, enlarged), 1);
                println!(
                    "{size} {alignment} {rust_region} {c_region} {wanted} {system_sum} {component_sum} {wrong}"
                );
            }
        }
        mi_heap_delete(second);
        mi_heap_delete(first);
    }
}
