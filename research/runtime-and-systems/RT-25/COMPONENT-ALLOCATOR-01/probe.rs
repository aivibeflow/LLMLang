use std::alloc::{GlobalAlloc, Layout, System};
use std::ffi::{c_char, c_int, c_void, CString};
use std::os::unix::ffi::OsStrExt;
use std::path::Path;
use std::ptr::{self, NonNull};
use std::slice;

#[global_allocator]
static GLOBAL: System = System;

mod bindings {
    #![allow(dead_code)]
    include!("../../PROTOTYPES/ALLOCATOR-COMPAT-01/probe.rs");

    pub fn check(expected: &std::path::Path) {
        let expected = expected.canonicalize().unwrap();
        for symbol in [
            malloc as *const c_void,
            calloc as *const c_void,
            realloc as *const c_void,
            free as *const c_void,
            posix_memalign as *const c_void,
        ] {
            assert_eq!(std::fs::canonicalize(provider(symbol)).unwrap(), expected);
        }
    }

    pub fn named(address: *const c_void, expected: &std::path::Path) {
        assert_eq!(std::fs::canonicalize(provider(address)).unwrap(), expected);
    }
}

unsafe extern "C" {
    fn dlopen(filename: *const c_char, flags: c_int) -> *mut c_void;
    fn dlsym(handle: *mut c_void, name: *const c_char) -> *mut c_void;
    fn dlclose(handle: *mut c_void) -> c_int;
}

type MiAlloc = unsafe extern "C" fn(usize, usize) -> *mut c_void;
type MiFree = unsafe extern "C" fn(*mut c_void);

struct Mimalloc {
    handle: NonNull<c_void>,
    alloc: MiAlloc,
    free: MiFree,
}

impl Mimalloc {
    fn open(path: &Path) -> Self {
        let real = path.canonicalize().unwrap();
        let filename = CString::new(real.as_os_str().as_bytes()).unwrap();
        const RTLD_NOW: c_int = 2;
        const RTLD_LOCAL: c_int = 0;
        // Safety: the path is NUL-terminated. Both symbol signatures match the pinned API.
        unsafe {
            let handle = NonNull::new(dlopen(filename.as_ptr(), RTLD_NOW | RTLD_LOCAL))
                .expect("load component allocator");
            let alloc = NonNull::new(dlsym(handle.as_ptr(), c"mi_malloc_aligned".as_ptr()))
                .expect("resolve mi_malloc_aligned");
            let free = NonNull::new(dlsym(handle.as_ptr(), c"mi_free".as_ptr()))
                .expect("resolve mi_free");
            bindings::named(alloc.as_ptr(), &real);
            bindings::named(free.as_ptr(), &real);
            Self {
                handle,
                alloc: std::mem::transmute::<*mut c_void, MiAlloc>(alloc.as_ptr()),
                free: std::mem::transmute::<*mut c_void, MiFree>(free.as_ptr()),
            }
        }
    }
}

impl Drop for Mimalloc {
    fn drop(&mut self) {
        // Live blocks borrow their component, which in turn borrows the library.
        assert_eq!(unsafe { dlclose(self.handle.as_ptr()) }, 0);
    }
}

enum Component<'a> {
    System,
    Mimalloc(&'a Mimalloc),
}

struct Block<'a> {
    owner: &'a Component<'a>,
    data: NonNull<u8>,
    layout: Layout,
}

impl<'a> Block<'a> {
    fn new(owner: &'a Component<'a>, layout: Layout, byte: u8) -> Self {
        assert_ne!(layout.size(), 0);
        // Safety: this layout has a nonzero size. Only the matching owner will deallocate it.
        let raw = unsafe {
            match owner {
                Component::System => System.alloc(layout),
                Component::Mimalloc(api) => (api.alloc)(layout.size(), layout.align()).cast(),
            }
        };
        let data = NonNull::new(raw).expect("allocation failed");
        let block = Self { owner, data, layout };
        assert_eq!(data.as_ptr() as usize % layout.align(), 0);
        unsafe { data.as_ptr().write_bytes(byte, layout.size()) };
        block
    }

    fn bytes(&self) -> &[u8] {
        // Every byte was initialized by new and the unique Block keeps it live.
        unsafe { slice::from_raw_parts(self.data.as_ptr(), self.layout.size()) }
    }

    fn release(self, caller: &Component<'_>) -> Result<(), Self> {
        if ptr::eq(self.owner, caller) {
            drop(self);
            Ok(())
        } else {
            Err(self)
        }
    }
}

impl Drop for Block<'_> {
    fn drop(&mut self) {
        // Safety: retain the allocator and layout chosen at allocation, even on implicit drop.
        unsafe {
            match self.owner {
                Component::System => System.dealloc(self.data.as_ptr(), self.layout),
                Component::Mimalloc(api) => (api.free)(self.data.as_ptr().cast()),
            }
        }
    }
}

fn main() {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    let [system, named] = args.as_slice() else {
        panic!("usage: probe SYSTEM_PROVIDER MIMALLOC_PROVIDER");
    };
    bindings::check(Path::new(system));
    let library = Mimalloc::open(Path::new(named));
    bindings::check(Path::new(system));
    let components = [Component::System, Component::Mimalloc(&library), Component::Mimalloc(&library)];
    let mut allocations = 0;
    let mut refusals = 0;
    let mut checksum = 0u64;
    for (source, from) in components.iter().enumerate() {
        for (destination, to) in components.iter().enumerate() {
            for size in [1, 7, 32, 128, 4095, 8192] {
                for alignment in [8, 16, 64, 256, 4096] {
                    let layout = Layout::from_size_align(size, alignment).unwrap();
                    let marker = (1 + size + alignment + 13 * source + 17 * destination) as u8;
                    let block = Block::new(from, layout, marker);
                    let copied = block.bytes().to_vec();
                    allocations += 1;
                    match block.release(to) {
                        Ok(()) => assert_eq!(source, destination),
                        Err(returned) => {
                            assert_ne!(source, destination);
                            assert_eq!(returned.bytes(), copied);
                            assert!(returned.release(from).is_ok());
                            refusals += 1;
                        }
                    }
                    assert!(copied.iter().all(|&byte| byte == marker));
                    checksum += (allocations as u64) * (size as u64 + u64::from(marker));
                }
            }
        }
    }
    bindings::check(Path::new(system));
    println!("{allocations},{refusals},{checksum}");
}

#[cfg(compile_fail_live_block)]
fn retire_provider_with_live_allocation(path: &Path) {
    let library = Mimalloc::open(path);
    let component = Component::Mimalloc(&library);
    let block = Block::new(&component, Layout::new::<u64>(), 1);
    drop(library);
    drop(block);
}
