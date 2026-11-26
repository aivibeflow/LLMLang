use super::{abi, decode_write, decode_zero, SyscallError};
use std::mem::{align_of, offset_of, size_of};

const STATMOUNT: usize = 457;
const LISTMOUNT: usize = 458;
const STATMOUNT_MNT_BASIC: u64 = 0x2;
const LSMT_ROOT: u64 = u64::MAX;
const MNT_UNIQUE_ID_OFFSET: u64 = 1 << 31;
const MAX_MOUNT_PAGE: usize = 1024;

/// The original request prefix selects the caller's current mount namespace.
/// The omitted trailing namespace ID is treated as zero by Linux.
#[repr(C)]
struct MountIdReq {
    size: u32,
    spare: u32,
    mount_id: u64,
    parameter: u64,
}

impl MountIdReq {
    fn new(mount_id: u64, parameter: u64) -> Self {
        Self {
            size: size_of::<Self>() as u32,
            spare: 0,
            mount_id,
            parameter,
        }
    }
}

#[repr(C)]
#[derive(Default)]
struct NativeMountPrefix {
    size: u32,
    mount_options: u32,
    mask: u64,
    device_major: u32,
    device_minor: u32,
    superblock_magic: u64,
    superblock_flags: u32,
    filesystem_type: u32,
    mount_id: u64,
    parent_mount_id: u64,
    legacy_id: u32,
    legacy_parent_id: u32,
    attributes: u64,
    propagation: u64,
    peer_group: u64,
    master_group: u64,
}

#[repr(C)]
struct NativeMountStat {
    prefix: NativeMountPrefix,
    tail: [u64; 52],
}

const _: () = {
    assert!(size_of::<MountIdReq>() == 24);
    assert!(align_of::<MountIdReq>() == 8);
    assert!(offset_of!(MountIdReq, mount_id) == 8);
    assert!(offset_of!(MountIdReq, parameter) == 16);
    assert!(size_of::<NativeMountPrefix>() == 96);
    assert!(offset_of!(NativeMountPrefix, mask) == 8);
    assert!(offset_of!(NativeMountPrefix, mount_id) == 40);
    assert!(offset_of!(NativeMountPrefix, legacy_id) == 56);
    assert!(offset_of!(NativeMountPrefix, master_group) == 88);
    assert!(size_of::<NativeMountStat>() == 512);
    assert!(align_of::<NativeMountStat>() == 8);
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MountBasic {
    pub mount_id: u64,
    pub parent_mount_id: u64,
    pub legacy_id: u32,
    pub legacy_parent_id: u32,
    pub attributes: u64,
    pub propagation: u64,
    pub peer_group: u64,
    pub master_group: u64,
}

/// Lists a page of mount IDs reachable from the current namespace root.
/// Use zero for the first page and its last ID as the next cursor. This
/// operation does not stabilize the mount tree between separate queries.
pub fn listmount(after: u64, capacity: usize) -> Result<Vec<u64>, SyscallError> {
    if capacity > MAX_MOUNT_PAGE {
        return Err(SyscallError::InvalidInput(
            "mount ID page is larger than 1024 entries",
        ));
    }
    if after == LSMT_ROOT {
        return Err(SyscallError::InvalidInput(
            "mount root selector is not a page cursor",
        ));
    }
    let request = MountIdReq::new(LSMT_ROOT, after);
    let mut mounts = vec![0_u64; capacity];
    let raw = unsafe {
        abi::invoke(
            LISTMOUNT,
            [
                (&request as *const MountIdReq) as usize,
                mounts.as_mut_ptr() as usize,
                capacity,
                0,
                0,
                0,
            ],
        )
    };
    let count = decode_write(raw, capacity)?;
    mounts.truncate(count);
    if mounts
        .first()
        .is_some_and(|id| *id <= after.max(MNT_UNIQUE_ID_OFFSET))
        || mounts.windows(2).any(|ids| ids[0] >= ids[1])
        || mounts.last() == Some(&LSMT_ROOT)
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(mounts)
}

/// Observes the basic attributes of one reachable mount in the caller's
/// namespace. It requests no strings, namespace selectors or mount changes.
pub fn statmount(mount_id: u64) -> Result<MountBasic, SyscallError> {
    let request = MountIdReq::new(mount_id, STATMOUNT_MNT_BASIC);
    let mut output = NativeMountStat {
        prefix: NativeMountPrefix::default(),
        tail: [0; 52],
    };
    let raw = unsafe {
        abi::invoke(
            STATMOUNT,
            [
                (&request as *const MountIdReq) as usize,
                (&mut output as *mut NativeMountStat) as usize,
                size_of::<NativeMountStat>(),
                0,
                0,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    let mount = output.prefix;
    let reported = mount.size as usize;
    if !(size_of::<NativeMountPrefix>()..=size_of::<NativeMountStat>()).contains(&reported)
        || mount.mask & STATMOUNT_MNT_BASIC == 0
        || mount.mount_id != mount_id
    {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(MountBasic {
        mount_id: mount.mount_id,
        parent_mount_id: mount.parent_mount_id,
        legacy_id: mount.legacy_id,
        legacy_parent_id: mount.legacy_parent_id,
        attributes: mount.attributes,
        propagation: mount.propagation,
        peer_group: mount.peer_group,
        master_group: mount.master_group,
    })
}
