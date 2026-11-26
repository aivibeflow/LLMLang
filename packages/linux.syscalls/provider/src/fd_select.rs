//! Native select and pselect6 for borrowed descriptor sets of up to 1024 bits.

use super::{abi, decode_nonnegative, IntervalDuration, SyscallError, Timespec};
use std::fmt;
use std::marker::PhantomData;
use std::os::fd::{AsRawFd, BorrowedFd, RawFd};
use std::ptr;

const SELECT: usize = 23;
const PSELECT6: usize = 270;
const DESCRIPTOR_BITS: usize = 1024;
const WORD_BITS: usize = u64::BITS as usize;
const WORDS: usize = DESCRIPTOR_BITS / WORD_BITS;

/// A native 1024-bit descriptor set that keeps every inserted fd borrowed.
///
/// ```compile_fail
/// use linux_syscalls_provider::{close, pipe2, SelectFdSet};
/// let (reader, _writer) = pipe2(0).unwrap();
/// let mut set = SelectFdSet::new();
/// set.insert(reader.borrow()).unwrap();
/// close(reader).unwrap();
/// assert!(!set.is_empty());
/// ```
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct SelectFdSet<'fd> {
    words: [u64; WORDS],
    borrowed: PhantomData<BorrowedFd<'fd>>,
}

impl<'fd> SelectFdSet<'fd> {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn insert(&mut self, fd: BorrowedFd<'fd>) -> Result<(), SyscallError> {
        let (word, bit) = position(fd.as_raw_fd()).ok_or(SyscallError::InvalidInput(
            "descriptor outside the select bit set",
        ))?;
        self.words[word] |= bit;
        Ok(())
    }

    pub fn contains(&self, fd: BorrowedFd<'_>) -> bool {
        position(fd.as_raw_fd()).is_some_and(|(word, bit)| self.words[word] & bit != 0)
    }

    pub fn is_empty(&self) -> bool {
        self.words.iter().all(|word| *word == 0)
    }

    fn count(self) -> usize {
        self.words
            .iter()
            .map(|word| word.count_ones() as usize)
            .sum()
    }

    fn is_subset(self, requested: Self) -> bool {
        self.words
            .into_iter()
            .zip(requested.words)
            .all(|(found, wanted)| found & !wanted == 0)
    }
}

fn position(fd: RawFd) -> Option<(usize, u64)> {
    if fd < 0 || fd as usize >= DESCRIPTOR_BITS {
        return None;
    }
    let index = fd as usize;
    Some((index / WORD_BITS, 1_u64 << (index % WORD_BITS)))
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct SelectFdSets<'fd> {
    pub read: SelectFdSet<'fd>,
    pub write: SelectFdSet<'fd>,
    pub exceptional: SelectFdSet<'fd>,
}

impl<'fd> SelectFdSets<'fd> {
    pub fn new() -> Self {
        Self::default()
    }

    fn nfds(self) -> usize {
        for word in (0..WORDS).rev() {
            let used =
                self.read.words[word] | self.write.words[word] | self.exceptional.words[word];
            if used != 0 {
                return (word + 1) * WORD_BITS - used.leading_zeros() as usize;
            }
        }
        0
    }

    fn count(self) -> usize {
        self.read.count() + self.write.count() + self.exceptional.count()
    }

    fn is_subset(self, requested: Self) -> bool {
        self.read.is_subset(requested.read)
            && self.write.is_subset(requested.write)
            && self.exceptional.is_subset(requested.exceptional)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SelectOutcome<T> {
    pub ready: usize,
    pub remaining: Option<T>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SelectError<T> {
    pub error: SyscallError,
    pub remaining: Option<T>,
}

impl<T> fmt::Display for SelectError<T> {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.error.fmt(formatter)
    }
}

impl<T: fmt::Debug> std::error::Error for SelectError<T> {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.error)
    }
}

/// Replaces the requested descriptor sets with their ready subsets on success.
/// A descriptor ready in two sets contributes two to the returned count. The
/// optional relative timeout has microsecond precision. The timeout snapshot
/// after the call is exposed on either outcome, including EINTR. Linux's
/// STICKY_TIMEOUTS personality can leave the original timeout unchanged.
pub fn select(
    sets: &mut SelectFdSets<'_>,
    mut timeout: Option<IntervalDuration>,
) -> Result<SelectOutcome<IntervalDuration>, SelectError<IntervalDuration>> {
    let timeout_ptr = timeout.as_mut().map_or(ptr::null_mut(), ptr::from_mut);
    let (raw, native) = wait(SELECT, *sets, timeout_ptr as usize);
    let remaining = timeout
        .map(|value| IntervalDuration::new(value.seconds(), value.micros()))
        .transpose();
    finish(raw, sets, native, remaining)
}

/// Like select, with a relative nanosecond timeout. The native pselect6 timeout
/// can be updated even on EINTR and is returned explicitly. The optional signal
/// mask argument is null, so this profile does not change the thread mask.
pub fn pselect6(
    sets: &mut SelectFdSets<'_>,
    mut timeout: Option<Timespec>,
) -> Result<SelectOutcome<Timespec>, SelectError<Timespec>> {
    let timeout_ptr = timeout.as_mut().map_or(ptr::null_mut(), ptr::from_mut);
    let (raw, native) = wait(PSELECT6, *sets, timeout_ptr as usize);
    let remaining = timeout
        .map(|value| {
            if raw >= 0 && value.seconds() < 0 {
                return Err(SyscallError::UnexpectedReturn(raw));
            }
            value.checked(raw)
        })
        .transpose();
    finish(raw, sets, native, remaining)
}

fn wait<'fd>(
    operation: usize,
    mut sets: SelectFdSets<'fd>,
    timeout: usize,
) -> (isize, SelectFdSets<'fd>) {
    let raw = unsafe {
        abi::invoke(
            operation,
            [
                sets.nfds(),
                sets.read.words.as_mut_ptr() as usize,
                sets.write.words.as_mut_ptr() as usize,
                sets.exceptional.words.as_mut_ptr() as usize,
                timeout,
                0,
            ],
        )
    };
    (raw, sets)
}

fn finish<'fd, T>(
    raw: isize,
    sets: &mut SelectFdSets<'fd>,
    native: SelectFdSets<'fd>,
    remaining: Result<Option<T>, SyscallError>,
) -> Result<SelectOutcome<T>, SelectError<T>> {
    let ready = match decode_nonnegative(raw) {
        Ok(ready) => ready,
        Err(error) => {
            return Err(SelectError {
                error,
                remaining: remaining.ok().flatten(),
            })
        }
    };
    let remaining = remaining.map_err(|_| SelectError {
        error: SyscallError::UnexpectedReturn(raw),
        remaining: None,
    })?;
    if !native.is_subset(*sets) || native.count() != ready {
        return Err(SelectError {
            error: SyscallError::UnexpectedReturn(raw),
            remaining,
        });
    }
    *sets = native;
    Ok(SelectOutcome { ready, remaining })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn select_bit_set_covers_exactly_1024_descriptors() {
        assert_eq!(std::mem::size_of::<[u64; WORDS]>(), 128);
        assert_eq!(position(-1), None);
        assert_eq!(position(0), Some((0, 1)));
        assert_eq!(position(1023), Some((15, 1_u64 << 63)));
        assert_eq!(position(1024), None);
        let mut sets = SelectFdSets::new();
        assert_eq!(sets.nfds(), 0);
        sets.exceptional.words[15] = 1_u64 << 63;
        assert_eq!(sets.nfds(), 1024);
    }
}
