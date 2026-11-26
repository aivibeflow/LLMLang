//! Anonymous, calling-thread session keyrings and their own user keys.

use super::{abi, decode_nonnegative, decode_zero, SyscallError};
use std::cell::Cell;
use std::ffi::{CStr, CString};
use std::marker::PhantomData;
use std::rc::Rc;

const ADD_KEY: usize = 248;
const REQUEST_KEY: usize = 249;
const KEYCTL: usize = 250;

const KEYCTL_JOIN_SESSION_KEYRING: usize = 1;
const KEYCTL_UNLINK: usize = 9;
const KEYCTL_READ: usize = 11;
const MAX_SUFFIX_BYTES: usize = 64;
const MAX_PAYLOAD_BYTES: usize = 1024;

thread_local! {
    static ENTERED: Cell<bool> = const { Cell::new(false) };
}

/// Authority for an anonymous session keyring installed by this calling thread.
/// This API cannot restore the former session. External code must not switch
/// the session or change the owned links behind the token.
#[derive(Debug)]
pub struct SessionKeyring {
    serial: i32,
    thread_affine: PhantomData<Rc<()>>,
}

fn serial(raw: isize) -> Result<i32, SyscallError> {
    let value = decode_nonnegative(raw)?;
    i32::try_from(value)
        .ok()
        .filter(|value| *value > 0)
        .ok_or(SyscallError::UnexpectedReturn(raw))
}

pub fn keyctl_join_session() -> Result<SessionKeyring, SyscallError> {
    if ENTERED.get() {
        return Err(SyscallError::InvalidInput(
            "an anonymous session keyring was already installed",
        ));
    }
    let serial =
        serial(unsafe { abi::call(KEYCTL, [KEYCTL_JOIN_SESSION_KEYRING, 0, 0, 0, 0, 0]) })?;
    ENTERED.set(true);
    Ok(SessionKeyring {
        serial,
        thread_affine: PhantomData,
    })
}

/// A key with one exact link in its exclusively borrowed session keyring.
/// Its serial and description cannot be supplied by another authority.
#[derive(Debug)]
pub struct OwnedUserKey<'ring> {
    ring: &'ring mut SessionKeyring,
    serial: i32,
    description: CString,
    payload_len: usize,
    linked: bool,
}

impl OwnedUserKey<'_> {
    fn check_linked(&self) -> Result<(), SyscallError> {
        if self.linked {
            Ok(())
        } else {
            Err(SyscallError::InvalidInput("the owned key was unlinked"))
        }
    }
}

impl Drop for OwnedUserKey<'_> {
    fn drop(&mut self) {
        if self.linked {
            let _ = keyctl_unlink(self);
        }
    }
}

fn check_description(description: &CStr) -> Result<(), SyscallError> {
    let suffix = description.to_bytes().strip_prefix(b"llmlang:");
    match suffix {
        Some(suffix)
            if !suffix.is_empty()
                && suffix.len() <= MAX_SUFFIX_BYTES
                && suffix
                    .iter()
                    .all(|byte| byte.is_ascii_alphanumeric() || b"._-".contains(byte)) =>
        {
            Ok(())
        }
        _ => Err(SyscallError::InvalidInput("invalid local key description")),
    }
}

/// Add a bounded `user` key to the exact owned ring.
pub fn add_key<'ring>(
    ring: &'ring mut SessionKeyring,
    description: &CStr,
    payload: &[u8],
) -> Result<OwnedUserKey<'ring>, SyscallError> {
    check_description(description)?;
    if payload.is_empty() || payload.len() > MAX_PAYLOAD_BYTES {
        return Err(SyscallError::InvalidInput(
            "invalid user key payload length",
        ));
    }
    let description = description.to_owned();
    let serial = serial(unsafe {
        abi::call(
            ADD_KEY,
            [
                c"user".as_ptr() as usize,
                description.as_ptr() as usize,
                payload.as_ptr() as usize,
                payload.len(),
                ring.serial as usize,
                0,
            ],
        )
    })?;
    Ok(OwnedUserKey {
        ring,
        serial,
        description,
        payload_len: payload.len(),
        linked: true,
    })
}

/// Confirm that ordinary no-callout lookup resolves exactly the owned key.
/// No destination ring is supplied, so the syscall cannot add a link.
pub fn request_key(key: &OwnedUserKey<'_>) -> Result<(), SyscallError> {
    key.check_linked()?;
    let found = serial(unsafe {
        abi::call(
            REQUEST_KEY,
            [
                c"user".as_ptr() as usize,
                key.description.as_ptr() as usize,
                0,
                0,
                0,
                0,
            ],
        )
    })?;
    if found == key.serial {
        Ok(())
    } else {
        Err(SyscallError::InvalidInput(
            "key lookup did not resolve to the owned key",
        ))
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum KeyReadOutcome {
    Written(usize),
    BufferTooSmall { required_bytes: usize },
}

/// Observe the complete value or its required size, preserving any output suffix.
pub fn keyctl_read(
    key: &OwnedUserKey<'_>,
    output: &mut [u8],
) -> Result<KeyReadOutcome, SyscallError> {
    key.check_linked()?;
    let mut data = [0_u8; MAX_PAYLOAD_BYTES];
    let capacity = output.len().min(data.len());
    let raw = unsafe {
        abi::call(
            KEYCTL,
            [
                KEYCTL_READ,
                key.serial as usize,
                data.as_mut_ptr() as usize,
                capacity,
                0,
                0,
            ],
        )
    };
    let required = decode_nonnegative(raw)?;
    if required != key.payload_len {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    if required > capacity {
        return Ok(KeyReadOutcome::BufferTooSmall {
            required_bytes: required,
        });
    }
    output[..required].copy_from_slice(&data[..required]);
    Ok(KeyReadOutcome::Written(required))
}

/// Remove exactly this key's link. This does not revoke other kernel references.
pub fn keyctl_unlink(key: &mut OwnedUserKey<'_>) -> Result<(), SyscallError> {
    key.check_linked()?;
    decode_zero(unsafe {
        abi::call(
            KEYCTL,
            [
                KEYCTL_UNLINK,
                key.serial as usize,
                key.ring.serial as usize,
                0,
                0,
                0,
            ],
        )
    })?;
    key.linked = false;
    Ok(())
}
