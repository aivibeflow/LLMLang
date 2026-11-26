//! Resource limits and thread affinity through the native Linux x86-64 ABI.
use crate::{abi, decode_nonnegative, decode_zero, Limit, LimitResource, Rlimit, SyscallError};

const SETRLIMIT: usize = 160;
const SCHED_SETAFFINITY: usize = 203;
const SCHED_GETAFFINITY: usize = 204;
const AFFINITY_WORDS: usize = 128;
const CPU_LIMIT: usize = AFFINITY_WORDS * u64::BITS as usize;

pub fn setrlimit(resource: LimitResource, limits: Rlimit) -> Result<(), SyscallError> {
    fn native(limit: Limit) -> Result<u64, SyscallError> {
        match limit {
            Limit::Unlimited => Ok(u64::MAX),
            Limit::Finite(u64::MAX) => Err(SyscallError::InvalidInput(
                "use Unlimited for the Linux infinity sentinel",
            )),
            Limit::Finite(value) => Ok(value),
        }
    }
    let soft = native(limits.soft)?;
    let hard = native(limits.hard)?;
    if soft > hard {
        return Err(SyscallError::InvalidInput(
            "the soft resource limit exceeds the hard limit",
        ));
    }
    let values = [soft, hard];
    decode_zero(unsafe {
        abi::call(
            SETRLIMIT,
            [resource as usize, values.as_ptr() as usize, 0, 0, 0, 0],
        )
    })
}

/// A CPU bitmap for Linux x86-64 kernels with at most 8192 CPU IDs.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CpuAffinity {
    words: [u64; AFFINITY_WORDS],
}

impl CpuAffinity {
    pub fn single(cpu: usize) -> Result<Self, SyscallError> {
        if cpu >= CPU_LIMIT {
            return Err(SyscallError::InvalidInput(
                "CPU ID exceeds the affinity profile",
            ));
        }
        let mut words = [0; AFFINITY_WORDS];
        words[cpu / 64] = 1 << (cpu % 64);
        Ok(Self { words })
    }

    pub fn first(&self) -> Option<usize> {
        self.words.iter().enumerate().find_map(|(index, word)| {
            (*word != 0).then(|| index * 64 + word.trailing_zeros() as usize)
        })
    }

    pub fn contains(&self, cpu: usize) -> bool {
        cpu < CPU_LIMIT && self.words[cpu / 64] & (1 << (cpu % 64)) != 0
    }
}

/// Observe affinity for the calling thread (native PID argument 0).
pub fn sched_getaffinity() -> Result<CpuAffinity, SyscallError> {
    let mut words = [0_u64; AFFINITY_WORDS];
    let size = std::mem::size_of_val(&words);
    let raw = unsafe {
        abi::call(
            SCHED_GETAFFINITY,
            [0, size, words.as_mut_ptr() as usize, 0, 0, 0],
        )
    };
    let written = decode_nonnegative(raw)?;
    if written == 0 || written > size || written % std::mem::size_of::<u64>() != 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(CpuAffinity { words })
}

/// Request affinity for the calling thread. Linux may intersect the mask with
/// the active and permitted CPU sets. Query to observe that intersection.
pub fn sched_setaffinity(affinity: &CpuAffinity) -> Result<(), SyscallError> {
    let size = std::mem::size_of_val(&affinity.words);
    decode_zero(unsafe {
        abi::call(
            SCHED_SETAFFINITY,
            [0, size, affinity.words.as_ptr() as usize, 0, 0, 0],
        )
    })
}
