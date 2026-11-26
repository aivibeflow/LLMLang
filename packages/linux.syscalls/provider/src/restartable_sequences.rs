//! Current-thread restartable-sequences storage with a null critical section.

use crate::{abi, decode_zero, SyscallError};
use std::{
    marker::PhantomData,
    ptr::NonNull,
    rc::Rc,
    sync::atomic::{AtomicU32, Ordering},
};

const RSEQ: usize = 334;
const RSEQ_FLAG_UNREGISTER: usize = 1;
const RSEQ_SIG: usize = 0x5305_3053;

#[repr(C, align(32))]
struct NativeRseq {
    cpu_id_start: AtomicU32,
    cpu_id: AtomicU32,
    rseq_cs: u64,
    flags: u32,
    node_id: u32,
    mm_cid: u32,
}

impl NativeRseq {
    fn new() -> Self {
        Self {
            cpu_id_start: AtomicU32::new(0),
            cpu_id: AtomicU32::new(u32::MAX),
            rseq_cs: 0,
            flags: 0,
            node_id: 0,
            mm_cid: 0,
        }
    }
}

const RSEQ_LEN: usize = 32;
const _: () = {
    assert!(size_of::<NativeRseq>() == RSEQ_LEN);
    assert!(align_of::<NativeRseq>() == RSEQ_LEN);
    assert!(std::mem::offset_of!(NativeRseq, cpu_id_start) == 0);
    assert!(std::mem::offset_of!(NativeRseq, cpu_id) == 4);
    assert!(std::mem::offset_of!(NativeRseq, rseq_cs) == 8);
    assert!(std::mem::offset_of!(NativeRseq, flags) == 16);
    assert!(std::mem::offset_of!(NativeRseq, node_id) == 20);
    assert!(std::mem::offset_of!(NativeRseq, mm_cid) == 24);
};

/// Owns a native rseq registration on its creating thread. The stable storage
/// remains private and the critical-section pointer stays null.
#[derive(Debug)]
pub struct RseqRegistration {
    storage: Option<NonNull<NativeRseq>>,
    thread: PhantomData<Rc<()>>,
}

impl RseqRegistration {
    /// Reports the most recent CPU ID published by the kernel. It can become
    /// stale immediately after the read if the thread migrates.
    pub fn cpu_id(&self) -> Option<u32> {
        let storage = self.storage?;
        // The kernel field is an aligned single-copy atomic u32. Do not make
        // a reference to the surrounding structure that the kernel may update.
        let cpu_id = unsafe { &*std::ptr::addr_of!((*storage.as_ptr()).cpu_id) };
        let value = cpu_id.load(Ordering::Relaxed);
        (value <= i32::MAX as u32).then_some(value)
    }

    fn unregister(&mut self) -> Result<(), SyscallError> {
        let Some(storage) = self.storage.take() else {
            return Ok(());
        };
        // If Linux refuses unregistering, the allocation must remain live.
        // The thread still owns the kernel registration until it exits.
        call(storage, RSEQ_FLAG_UNREGISTER)?;
        // Linux has removed the pointer from the current thread.
        drop(unsafe { Box::from_raw(storage.as_ptr()) });
        Ok(())
    }
}

impl Drop for RseqRegistration {
    fn drop(&mut self) {
        let _ = self.unregister();
    }
}

fn call(storage: NonNull<NativeRseq>, flags: usize) -> Result<(), SyscallError> {
    let raw = unsafe {
        abi::invoke(
            RSEQ,
            [storage.as_ptr() as usize, RSEQ_LEN, flags, RSEQ_SIG, 0, 0],
        )
    };
    decode_zero(raw)
}

/// Registers a new private rseq area on the current thread. The thread must
/// have no pre-existing runtime registration for Linux to accept it.
pub fn rseq() -> Result<RseqRegistration, SyscallError> {
    let storage = NonNull::from(Box::leak(Box::new(NativeRseq::new())));
    if let Err(error) = call(storage, 0) {
        // A Linux registration failure leaves the prior per-thread pointer unchanged.
        drop(unsafe { Box::from_raw(storage.as_ptr()) });
        return Err(error);
    }
    Ok(RseqRegistration {
        storage: Some(storage),
        thread: PhantomData,
    })
}

/// Removes the owned registration from the same thread that created it.
pub fn rseq_unregister(mut registration: RseqRegistration) -> Result<(), SyscallError> {
    registration.unregister()
}
