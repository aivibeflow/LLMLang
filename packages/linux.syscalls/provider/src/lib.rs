//! Typed adapters for the native Linux x86-64 syscall ABI.
//!
//! Each operation exposes its individual syscall result and leaves retry and
//! partial-progress policy to its caller. Owned Linux descriptors are consumed
//! by `close` and borrowed by operations that leave ownership unchanged.

#[cfg(not(all(target_os = "linux", target_arch = "x86_64", target_pointer_width = "64")))]
compile_error!("linux.syscalls requires the native Linux x86-64 ABI");

mod abi;
mod bpf_array;
mod cache_range;
mod clock_observation;
mod clock_setting;
mod commands;
mod complex;
mod credential_changes;
mod credentials;
mod descriptor_slots;
mod directory_legacy;
mod fanotify;
mod fd;
mod fd_select;
mod file_page_mapping;
mod file_storage;
mod files_extra2;
mod files_extra;
mod filesystem;
mod filesystem_handles;
mod futex;
mod guest_controls;
mod inotify;
mod io;
mod kernel_modules;
mod keyring;
mod landlock;
mod legacy_aio;
mod legacy_time;
mod legacy_ustat;
mod lsm_queries;
mod memory;
mod memory_pages;
mod message_queue;
mod metadata_extra;
mod mount_queries;
mod mounts;
mod numa;
mod path_env;
mod pidfd;
mod pipe_transfer;
mod posix_timer;
mod priority_settings;
mod process;
mod process_extra;
mod process_lifecycle;
mod process_observation;
mod process_query;
mod process_settings;
mod pty_hangup;
mod quota_format;
mod restart;
mod restartable_sequences;
mod scheduler_policy;
mod sealed_memory;
mod seccomp_queries;
mod self_memory_transfer;
mod signal_action;
mod signal_control;
mod signal_fd;
mod signal_wait;
mod socket;
mod socket_batch;
mod socket_extra;
mod socket_messages;
mod swap;
mod system;
mod system_legacy;
mod sysv_message;
mod sysv_semaphore;
mod sysv_shm;
mod thread_architecture;
mod time_ipc;
mod trace_me;
mod udp;
mod uts;
mod vector_position;
mod uretprobe;
mod wait;
mod wait_extra;
mod xattr;

pub use bpf_array::*;
pub use cache_range::*;
pub use clock_observation::*;
pub use clock_setting::*;
pub use commands::*;
pub use complex::*;
pub use credential_changes::*;
pub use credentials::*;
pub use descriptor_slots::*;
pub use directory_legacy::*;
pub use fanotify::*;
pub use fd::*;
pub use fd_select::*;
pub use file_page_mapping::*;
pub use file_storage::*;
pub use files_extra2::*;
pub use files_extra::*;
pub use filesystem::*;
pub use filesystem_handles::*;
pub use futex::*;
pub use guest_controls::*;
pub use inotify::*;
pub use io::*;
pub use kernel_modules::*;
pub use keyring::*;
pub use landlock::*;
pub use legacy_aio::*;
pub use legacy_time::*;
pub use legacy_ustat::*;
pub use lsm_queries::*;
pub use memory::*;
pub use memory_pages::*;
pub use message_queue::*;
pub use metadata_extra::*;
pub use mount_queries::*;
pub use mounts::*;
pub use numa::*;
pub use path_env::*;
pub use pidfd::*;
pub use pipe_transfer::*;
pub use posix_timer::*;
pub use priority_settings::*;
pub use process::*;
pub use process_extra::*;
pub use process_lifecycle::*;
pub use process_observation::*;
pub use process_query::*;
pub use process_settings::*;
pub use pty_hangup::*;
pub use quota_format::*;
pub use restart::*;
pub use restartable_sequences::*;
pub use scheduler_policy::*;
pub use sealed_memory::*;
pub use seccomp_queries::*;
pub use self_memory_transfer::*;
pub use signal_action::*;
pub use signal_control::*;
pub use signal_fd::*;
pub use signal_wait::*;
pub use socket::*;
pub use socket_batch::*;
pub use socket_extra::*;
pub use socket_messages::*;
pub use swap::*;
pub use system::*;
pub use system_legacy::*;
pub use sysv_message::*;
pub use sysv_semaphore::*;
pub use sysv_shm::*;
pub use thread_architecture::*;
pub use time_ipc::*;
pub use trace_me::*;
pub use udp::*;
pub use uts::*;
pub use vector_position::*;
pub use uretprobe::*;
pub use wait::*;
pub use wait_extra::*;
pub use xattr::*;

use std::fmt;

pub const EINTR: i32 = 4;
pub const EBADF: i32 = 9;
pub const EAGAIN: i32 = 11;
pub const EINVAL: i32 = 22;
pub const EPIPE: i32 = 32;
pub const ENOSYS: i32 = 38;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Errno(i32);

impl Errno {
    pub fn code(self) -> i32 {
        self.0
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SyscallError {
    Kernel(Errno),
    UnexpectedReturn(isize),
    InvalidInput(&'static str),
}

impl SyscallError {
    pub fn is_errno(self, code: i32) -> bool {
        matches!(self, Self::Kernel(errno) if errno.code() == code)
    }
}

impl fmt::Display for SyscallError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Kernel(errno) => write!(f, "Linux errno {}", errno.code()),
            Self::UnexpectedReturn(raw) => write!(f, "unexpected Linux syscall result {raw}"),
            Self::InvalidInput(message) => f.write_str(message),
        }
    }
}

impl std::error::Error for SyscallError {}

fn decode_nonnegative(raw: isize) -> Result<usize, SyscallError> {
    match raw {
        -4095..=-1 => Err(SyscallError::Kernel(Errno((-raw) as i32))),
        0.. => Ok(raw as usize),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}

fn decode_zero(raw: isize) -> Result<(), SyscallError> {
    match decode_nonnegative(raw)? {
        0 => Ok(()),
        _ => Err(SyscallError::UnexpectedReturn(raw)),
    }
}
