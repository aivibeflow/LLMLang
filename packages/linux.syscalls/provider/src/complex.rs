//! Scoped task-clock and io_uring probes for Linux v6.12.

use super::{abi, decode_nonnegative, decode_zero, LinuxFd, SyscallError};
use std::ffi::CStr;
use std::mem::{align_of, offset_of, size_of};
use std::os::fd::{AsRawFd, BorrowedFd};
use std::ptr::{read_volatile, write_volatile, NonNull};
use std::sync::atomic::{AtomicU32, Ordering};

const PERF_EVENT_OPEN: usize = 298;
const IO_URING_SETUP: usize = 425;
const IO_URING_ENTER: usize = 426;
const IO_URING_REGISTER: usize = 427;

const PERF_TYPE_SOFTWARE: u32 = 1;
const PERF_COUNT_SW_TASK_CLOCK: u64 = 1;
const PERF_FLAG_FD_CLOEXEC: usize = 1 << 3;
const PERF_EXCLUDE_KERNEL: u64 = 1 << 5;
const PERF_EXCLUDE_HYPERVISOR: u64 = 1 << 6;
const PERF_ATTR_SIZE_VER0: u32 = 64;
const IORING_REGISTER_PROBE: usize = 8;
const MAX_PROBE_OPERATIONS: usize = 256;
const MAX_RING_ENTRIES: u32 = 256;
const IORING_FEAT_SINGLE_MMAP: u32 = 1;
const IORING_OFF_SQ_RING: usize = 0;
const IORING_OFF_SQES: usize = 0x1000_0000;
const IORING_ENTER_GETEVENTS: usize = 1;
const MAX_NOP_RING_BYTES: usize = 65_536;
const NOP_TAG: u64 = 1;

#[repr(C)]
#[derive(Default)]
struct PerfEventAttrV0 {
    event_type: u32,
    size: u32,
    config: u64,
    sample_period: u64,
    sample_type: u64,
    read_format: u64,
    flags: u64,
    wakeup_events: u32,
    breakpoint_type: u32,
    config1: u64,
}

/// Opens an active, unsampled software task clock for the calling thread.
/// The attributes request kernel and hypervisor exclusion. The observed count
/// follows the kernel's task-context clock semantics.
pub fn perf_event_open_task_clock() -> Result<LinuxFd, SyscallError> {
    let mut attributes = PerfEventAttrV0 {
        event_type: PERF_TYPE_SOFTWARE,
        size: PERF_ATTR_SIZE_VER0,
        config: PERF_COUNT_SW_TASK_CLOCK,
        flags: PERF_EXCLUDE_KERNEL | PERF_EXCLUDE_HYPERVISOR,
        ..PerfEventAttrV0::default()
    };
    // PID 0 selects this thread, CPU -1 selects any CPU, and group -1
    // creates a standalone event. The kernel can update the size on error.
    let raw = unsafe {
        abi::invoke(
            PERF_EVENT_OPEN,
            [
                (&mut attributes as *mut PerfEventAttrV0) as usize,
                0,
                -1_i32 as usize,
                -1_i32 as usize,
                PERF_FLAG_FD_CLOEXEC,
                0,
            ],
        )
    };
    LinuxFd::from_result(raw)
}

#[repr(C)]
struct PerfUprobeAttr {
    base: PerfEventAttrV0,
    probe_offset: u64,
}

const _: () = {
    assert!(size_of::<PerfUprobeAttr>() == 72);
    assert!(offset_of!(PerfUprobeAttr, probe_offset) == 64);
    assert!(offset_of!(PerfEventAttrV0, config1) == 56);
};

pub(super) fn perf_event_open_uprobe(
    event_type: u32,
    executable: &CStr,
    probe_offset: u64,
) -> Result<LinuxFd, SyscallError> {
    const RETPROBE: u64 = 1;
    let mut attributes = PerfUprobeAttr {
        base: PerfEventAttrV0 {
            event_type,
            size: size_of::<PerfUprobeAttr>() as u32,
            config: RETPROBE,
            config1: executable.as_ptr() as usize as u64,
            ..PerfEventAttrV0::default()
        },
        probe_offset,
    };
    // The selected standalone event counts only the calling thread. The
    // kernel copies the retained executable path during perf_event_open.
    let raw = unsafe {
        abi::invoke(
            PERF_EVENT_OPEN,
            [
                (&mut attributes as *mut PerfUprobeAttr) as usize,
                0,
                -1_i32 as usize,
                -1_i32 as usize,
                PERF_FLAG_FD_CLOEXEC,
                0,
            ],
        )
    };
    LinuxFd::from_result(raw)
}

#[repr(C)]
#[derive(Default)]
struct SqRingOffsets {
    head: u32,
    tail: u32,
    mask: u32,
    entries: u32,
    flags: u32,
    dropped: u32,
    array: u32,
    reserved: u32,
    user_addr: u64,
}

#[repr(C)]
#[derive(Default)]
struct CqRingOffsets {
    head: u32,
    tail: u32,
    mask: u32,
    entries: u32,
    overflow: u32,
    cqes: u32,
    flags: u32,
    reserved: u32,
    user_addr: u64,
}

#[repr(C)]
#[derive(Default)]
struct IoUringParams {
    sq_entries: u32,
    cq_entries: u32,
    flags: u32,
    sq_thread_cpu: u32,
    sq_thread_idle: u32,
    features: u32,
    wq_fd: u32,
    reserved: [u32; 3],
    sq_offsets: SqRingOffsets,
    cq_offsets: CqRingOffsets,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct IoUringInfo {
    pub submission_entries: u32,
    pub completion_entries: u32,
    pub features: u32,
}

/// Creates a small ring with default flags and yields an owned close-on-exec
/// descriptor and the kernel's reported queue capacities and features.
pub fn io_uring_setup(entries: u32) -> Result<(LinuxFd, IoUringInfo), SyscallError> {
    let (fd, params) = setup_ring(entries)?;
    Ok((
        fd,
        IoUringInfo {
            submission_entries: params.sq_entries,
            completion_entries: params.cq_entries,
            features: params.features,
        },
    ))
}

fn setup_ring(entries: u32) -> Result<(LinuxFd, IoUringParams), SyscallError> {
    if !(1..=MAX_RING_ENTRIES).contains(&entries) {
        return Err(SyscallError::InvalidInput(
            "io_uring depth must be in 1..=256 for this profile",
        ));
    }
    let mut params = IoUringParams::default();
    let raw = unsafe {
        abi::invoke(
            IO_URING_SETUP,
            [
                entries as usize,
                (&mut params as *mut IoUringParams) as usize,
                0,
                0,
                0,
                0,
            ],
        )
    };
    let fd = LinuxFd::from_result(raw)?;
    let rounded = entries.next_power_of_two();
    if params.sq_entries != rounded || params.cq_entries != rounded * 2 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok((fd, params))
}

#[repr(C)]
#[derive(Default)]
struct NativeSqe {
    opcode: u8,
    flags: u8,
    priority: u16,
    descriptor: i32,
    offset: u64,
    address: u64,
    len: u32,
    operation_flags: u32,
    user_data: u64,
    buffer_index: u16,
    personality: u16,
    splice_descriptor: i32,
    address3: u64,
    reserved: u64,
}

#[repr(C)]
struct NativeCqe {
    user_data: u64,
    result: i32,
    flags: u32,
}

struct RingMapping {
    base: NonNull<u8>,
    len: usize,
}

impl RingMapping {
    fn map(fd: &LinuxFd, len: usize, offset: usize) -> Result<Self, SyscallError> {
        const PROT_READ_WRITE: usize = 3;
        const MAP_SHARED: usize = 1;
        let raw = unsafe {
            abi::invoke(
                abi::MMAP,
                [
                    0,
                    len,
                    PROT_READ_WRITE,
                    MAP_SHARED,
                    fd.as_raw_fd() as usize,
                    offset,
                ],
            )
        };
        let address = decode_nonnegative(raw)?;
        let Some(base) = NonNull::new(address as *mut u8) else {
            let _ = unsafe { abi::invoke(abi::MUNMAP, [address, len, 0, 0, 0, 0]) };
            return Err(SyscallError::UnexpectedReturn(raw));
        };
        Ok(Self { base, len })
    }

    // The caller selects a naturally aligned field in the validated region.
    unsafe fn field<T>(&self, offset: u32) -> *mut T {
        unsafe { self.base.as_ptr().add(offset as usize).cast() }
    }
}

impl Drop for RingMapping {
    fn drop(&mut self) {
        let _ = unsafe {
            abi::invoke(
                abi::MUNMAP,
                [self.base.as_ptr() as usize, self.len, 0, 0, 0, 0],
            )
        };
    }
}

fn nop_ring_len(params: &IoUringParams) -> Result<usize, SyscallError> {
    let sq = &params.sq_offsets;
    let cq = &params.cq_offsets;
    if params.flags != 0
        || params.sq_entries != 1
        || params.cq_entries != 2
        || params.features & IORING_FEAT_SINGLE_MMAP == 0
        || sq.user_addr != 0
        || cq.user_addr != 0
        || sq.reserved != 0
        || cq.reserved != 0
    {
        return Err(SyscallError::InvalidInput(
            "io_uring NOP requires a default single-mapped depth-one ring",
        ));
    }
    let cq_start = cq.cqes as usize;
    let cq_end = cq_start + size_of::<NativeCqe>() * params.cq_entries as usize;
    let mut words = [
        sq.head,
        sq.tail,
        sq.mask,
        sq.entries,
        sq.flags,
        sq.dropped,
        sq.array,
        cq.head,
        cq.tail,
        cq.mask,
        cq.entries,
        cq.overflow,
        cq.flags,
    ]
    .map(|offset| offset as usize);
    words.sort_unstable();
    if cq_start % align_of::<NativeCqe>() != 0
        || words.windows(2).any(|pair| pair[0] == pair[1])
        || words
            .iter()
            .any(|offset| offset % align_of::<u32>() != 0 || (cq_start..cq_end).contains(offset))
    {
        return Err(SyscallError::InvalidInput(
            "overlapping or unaligned io_uring offsets",
        ));
    }
    let len = cq_end.max(words[words.len() - 1] + size_of::<u32>());
    if len > MAX_NOP_RING_BYTES {
        return Err(SyscallError::InvalidInput(
            "io_uring NOP mapping exceeds the profile size bound",
        ));
    }
    Ok(len)
}

/// Creates a fresh private ring, submits one pointer-free NOP and observes
/// its tagged completion. The enter call waits for one completion without a
/// userspace deadline. The descriptor and mappings stay inside this call.
pub fn io_uring_nop() -> Result<(), SyscallError> {
    let (fd, params) = setup_ring(1)?;
    let ring = RingMapping::map(&fd, nop_ring_len(&params)?, IORING_OFF_SQ_RING)?;
    let sqes = RingMapping::map(&fd, size_of::<NativeSqe>(), IORING_OFF_SQES)?;
    let sq = &params.sq_offsets;
    let cq = &params.cq_offsets;
    // The ring fields are disjoint, aligned and inside the mapped region.
    // The kernel and client use native-width acquire/release head and tail.
    let sq_head = unsafe { AtomicU32::from_ptr(ring.field(sq.head)) };
    let sq_tail = unsafe { AtomicU32::from_ptr(ring.field(sq.tail)) };
    let cq_head = unsafe { AtomicU32::from_ptr(ring.field(cq.head)) };
    let cq_tail = unsafe { AtomicU32::from_ptr(ring.field(cq.tail)) };
    let geometry = unsafe {
        [
            read_volatile(ring.field::<u32>(sq.mask)),
            read_volatile(ring.field::<u32>(sq.entries)),
            read_volatile(ring.field::<u32>(cq.mask)),
            read_volatile(ring.field::<u32>(cq.entries)),
        ]
    };
    if geometry != [0, 1, 1, 2]
        || [sq_head, sq_tail, cq_head, cq_tail]
            .iter()
            .any(|index| index.load(Ordering::Acquire) != 0)
    {
        return Err(SyscallError::InvalidInput(
            "io_uring NOP ring geometry or initial indices disagree",
        ));
    }

    // Zero opcode and unused fields specify IORING_OP_NOP. Neither the
    // caller nor the SQE supplies memory addresses or an open file.
    unsafe {
        write_volatile(
            sqes.field(0),
            NativeSqe {
                descriptor: -1,
                user_data: NOP_TAG,
                ..NativeSqe::default()
            },
        );
        write_volatile(ring.field(sq.array), 0_u32);
    }
    sq_tail.store(1, Ordering::Release);
    let raw = unsafe {
        abi::invoke(
            IO_URING_ENTER,
            [fd.as_raw_fd() as usize, 1, 1, IORING_ENTER_GETEVENTS, 0, 0],
        )
    };
    if decode_nonnegative(raw)? != 1
        || sq_head.load(Ordering::Acquire) != 1
        || cq_tail.load(Ordering::Acquire) != 1
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    let completion = unsafe { read_volatile(ring.field::<NativeCqe>(cq.cqes)) };
    if completion.user_data != NOP_TAG || completion.flags != 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    cq_head.store(1, Ordering::Release);
    decode_zero(completion.result as isize)
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct NativeProbeOp {
    opcode: u8,
    reserved: u8,
    flags: u16,
    reserved2: u32,
}

#[repr(C)]
struct NativeProbe {
    last_opcode: u8,
    operation_count: u8,
    reserved: u16,
    reserved2: [u32; 3],
    operations: [NativeProbeOp; MAX_PROBE_OPERATIONS],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct IoUringOpcode {
    pub opcode: u8,
    pub flags: u16,
}

#[derive(Debug, Eq, PartialEq)]
pub struct IoUringProbe {
    pub last_opcode: u8,
    pub operations: Vec<IoUringOpcode>,
}

/// Queries a ring's opcode metadata using the fixed IORING_REGISTER_PROBE
/// command and returns a bounded copy of the kernel's response.
pub fn io_uring_register_probe(ring: BorrowedFd<'_>) -> Result<IoUringProbe, SyscallError> {
    let mut probe = NativeProbe {
        last_opcode: 0,
        operation_count: 0,
        reserved: 0,
        reserved2: [0; 3],
        operations: [NativeProbeOp::default(); MAX_PROBE_OPERATIONS],
    };
    let raw = unsafe {
        abi::invoke(
            IO_URING_REGISTER,
            [
                ring.as_raw_fd() as usize,
                IORING_REGISTER_PROBE,
                (&mut probe as *mut NativeProbe) as usize,
                MAX_PROBE_OPERATIONS,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let count = usize::from(probe.operation_count);
    let entries = &probe.operations[..count];
    if count != usize::from(probe.last_opcode) + 1
        || entries
            .iter()
            .enumerate()
            .any(|(index, op)| usize::from(op.opcode) != index)
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    let operations = entries
        .iter()
        .map(|op| IoUringOpcode {
            opcode: op.opcode,
            flags: op.flags,
        })
        .collect();
    Ok(IoUringProbe {
        last_opcode: probe.last_opcode,
        operations,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem::{align_of, offset_of, size_of};

    #[test]
    fn complex_native_structures_match_v612_uapi() {
        assert_eq!(size_of::<PerfEventAttrV0>(), PERF_ATTR_SIZE_VER0 as usize);
        assert_eq!(align_of::<PerfEventAttrV0>(), 8);
        assert_eq!(offset_of!(PerfEventAttrV0, flags), 40);
        assert_eq!(offset_of!(PerfEventAttrV0, config1), 56);
        assert_eq!(size_of::<SqRingOffsets>(), 40);
        assert_eq!(size_of::<CqRingOffsets>(), 40);
        assert_eq!(offset_of!(SqRingOffsets, user_addr), 32);
        assert_eq!(offset_of!(CqRingOffsets, user_addr), 32);
        assert_eq!(size_of::<IoUringParams>(), 120);
        assert_eq!(align_of::<IoUringParams>(), 8);
        assert_eq!(offset_of!(IoUringParams, features), 20);
        assert_eq!(offset_of!(IoUringParams, sq_offsets), 40);
        assert_eq!(offset_of!(IoUringParams, cq_offsets), 80);
        assert_eq!(size_of::<NativeProbeOp>(), 8);
        assert_eq!(offset_of!(NativeProbeOp, flags), 2);
        assert_eq!(offset_of!(NativeProbe, operations), 16);
        assert_eq!(size_of::<NativeProbe>(), 16 + 8 * MAX_PROBE_OPERATIONS);
        assert_eq!(size_of::<NativeSqe>(), 64);
        assert_eq!(align_of::<NativeSqe>(), 8);
        assert_eq!(offset_of!(NativeSqe, user_data), 32);
        assert_eq!(offset_of!(NativeSqe, address3), 48);
        assert_eq!(size_of::<NativeCqe>(), 16);
        assert_eq!(align_of::<NativeCqe>(), 8);
        assert_eq!(offset_of!(NativeCqe, result), 8);
        assert_eq!(align_of::<AtomicU32>(), align_of::<u32>());
    }

    #[test]
    fn io_uring_nop_rejects_invalid_layout() {
        let mut params = IoUringParams {
            sq_entries: 1,
            cq_entries: 2,
            features: IORING_FEAT_SINGLE_MMAP,
            sq_offsets: SqRingOffsets {
                head: 0,
                tail: 4,
                mask: 8,
                entries: 12,
                flags: 16,
                dropped: 20,
                array: 128,
                ..SqRingOffsets::default()
            },
            cq_offsets: CqRingOffsets {
                head: 24,
                tail: 28,
                mask: 32,
                entries: 36,
                overflow: 40,
                flags: 44,
                cqes: 64,
                ..CqRingOffsets::default()
            },
            ..IoUringParams::default()
        };
        assert_eq!(nop_ring_len(&params), Ok(132));
        for invalid in [0, 65, 80, MAX_NOP_RING_BYTES as u32] {
            params.sq_offsets.array = invalid;
            assert!(matches!(
                nop_ring_len(&params),
                Err(SyscallError::InvalidInput(_))
            ));
        }
        params.sq_offsets.array = 128;
        params.features = 0;
        assert!(matches!(
            nop_ring_len(&params),
            Err(SyscallError::InvalidInput(_))
        ));
    }
}
