use super::{abi, decode_nonnegative, decode_zero, Errno, Mapping, SyscallError};
use std::mem::{align_of, size_of};

const MBIND: usize = 237;
const SET_MEMPOLICY: usize = 238;
const GET_MEMPOLICY: usize = 239;
const MIGRATE_PAGES: usize = 256;
const MOVE_PAGES: usize = 279;
const SET_MEMPOLICY_HOME_NODE: usize = 450;
const PAGE_SIZE: usize = 4096;
const MAX_PAGE_QUERIES: usize = 1024;
const MPOL_DEFAULT: usize = 0;
const MPOL_BIND: usize = 2;
const MPOL_INTERLEAVE: usize = 3;
const MPOL_LOCAL: usize = 4;
const MPOL_F_ADDR: usize = 1 << 1;
const MPOL_F_MEMS_ALLOWED: usize = 1 << 2;
const NODE_BITS: usize = 1024;
const NODE_WORDS: usize = NODE_BITS / u64::BITS as usize;
// The Linux nodemask implementation reads or writes maxnode - 1 bits.
const MAXNODE: usize = NODE_BITS + 1;

#[repr(transparent)]
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct NumaNodeMask([u64; NODE_WORDS]);

const _: () = {
    assert!(size_of::<NumaNodeMask>() == 128);
    assert!(align_of::<NumaNodeMask>() == 8);
};

impl NumaNodeMask {
    pub fn from_nodes(nodes: &[u16]) -> Result<Self, SyscallError> {
        let mut mask = Self::default();
        for &node in nodes {
            let node = usize::from(node);
            let word = mask
                .0
                .get_mut(node / u64::BITS as usize)
                .ok_or(SyscallError::InvalidInput("NUMA node index exceeds 1023"))?;
            *word |= 1 << (node % u64::BITS as usize);
        }
        Ok(mask)
    }

    pub fn contains(&self, node: u16) -> bool {
        let node = usize::from(node);
        self.0
            .get(node / u64::BITS as usize)
            .is_some_and(|word| word & (1 << (node % u64::BITS as usize)) != 0)
    }

    pub fn is_empty(&self) -> bool {
        self.0.iter().all(|word| *word == 0)
    }

    fn is_subset_of(&self, allowed: &Self) -> bool {
        self.0
            .iter()
            .zip(&allowed.0)
            .all(|(word, allowed_word)| word & !allowed_word == 0)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum NumaPolicy {
    Default,
    Local,
    Bind(NumaNodeMask),
    Interleave(NumaNodeMask),
}

impl NumaPolicy {
    fn arguments(&self) -> (usize, usize, usize) {
        match self {
            Self::Default => (MPOL_DEFAULT, 0, 0),
            Self::Local => (MPOL_LOCAL, 0, 0),
            Self::Bind(nodes) => (MPOL_BIND, nodes.0.as_ptr() as usize, MAXNODE),
            Self::Interleave(nodes) => (MPOL_INTERLEAVE, nodes.0.as_ptr() as usize, MAXNODE),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NumaPolicyState {
    /// The native mode and any mode flag bits returned by Linux.
    pub mode: i32,
    pub nodes: NumaNodeMask,
}

fn policy_at(address: usize, flags: usize) -> Result<NumaPolicyState, SyscallError> {
    let mut mode = -1_i32;
    let mut nodes = NumaNodeMask::default();
    let raw = unsafe {
        abi::call(
            GET_MEMPOLICY,
            [
                (&mut mode as *mut i32) as usize,
                nodes.0.as_mut_ptr() as usize,
                MAXNODE,
                address,
                flags,
                0,
            ],
        )
    };
    decode_zero(raw)?;
    if mode < 0 {
        return Err(SyscallError::UnexpectedReturn(raw));
    }
    Ok(NumaPolicyState { mode, nodes })
}

/// Observes the calling thread's memory placement policy and node mask.
pub fn get_mempolicy() -> Result<NumaPolicyState, SyscallError> {
    policy_at(0, 0)
}

/// Observes the allowed memory nodes of the calling thread's cpuset.
pub fn get_mempolicy_allowed() -> Result<NumaNodeMask, SyscallError> {
    Ok(policy_at(0, MPOL_F_MEMS_ALLOWED)?.nodes)
}

/// Observes the policy at the start of this owned private mapping without
/// falling back to the calling thread's policy.
pub fn get_mempolicy_mapping(mapping: &Mapping) -> Result<NumaPolicyState, SyscallError> {
    let region = mapping.as_slice();
    if region.is_empty() {
        return Err(SyscallError::InvalidInput("mapping has no live region"));
    }
    policy_at(region.as_ptr() as usize, MPOL_F_ADDR)
}

/// Changes the calling thread's policy for subsequent allocation decisions.
pub fn set_mempolicy(policy: &NumaPolicy) -> Result<(), SyscallError> {
    let (mode, mask, maxnode) = policy.arguments();
    decode_zero(unsafe { abi::call(SET_MEMPOLICY, [mode, mask, maxnode, 0, 0, 0]) })
}

/// Applies the selected policy to the full owned private mapping. The
/// adapter supplies no migration, strict-check or other mbind flags.
pub fn mbind(mapping: &mut Mapping, policy: &NumaPolicy) -> Result<(), SyscallError> {
    let region = mapping.as_slice();
    if region.is_empty() {
        return Err(SyscallError::InvalidInput("mapping has no live region"));
    }
    let (mode, mask, maxnode) = policy.arguments();
    decode_zero(unsafe {
        abi::call(
            MBIND,
            [
                region.as_ptr() as usize,
                region.len(),
                mode,
                mask,
                maxnode,
                0,
            ],
        )
    })
}

/// Reports Linux's NUMA node or per-page errno for 1 to 1024 page-aligned
/// byte offsets in this mapping, in the order supplied by the caller.
/// This invokes the current-process query with no destination nodes.
pub fn move_pages(
    mapping: &Mapping,
    page_offsets: &[usize],
) -> Result<Vec<Result<u16, Errno>>, SyscallError> {
    if !(1..=MAX_PAGE_QUERIES).contains(&page_offsets.len()) {
        return Err(SyscallError::InvalidInput(
            "page query count must be in 1..=1024",
        ));
    }

    let region = mapping.as_slice();
    let pages = page_offsets
        .iter()
        .map(|&offset| {
            if offset >= region.len() || offset % PAGE_SIZE != 0 {
                return Err(SyscallError::InvalidInput(
                    "page offset must be aligned and within the mapping",
                ));
            }
            Ok(region.as_ptr().wrapping_add(offset))
        })
        .collect::<Result<Vec<_>, _>>()?;
    let mut statuses = vec![i32::MIN; pages.len()];
    decode_zero(unsafe {
        abi::call(
            MOVE_PAGES,
            [
                0,
                pages.len(),
                pages.as_ptr() as usize,
                0,
                statuses.as_mut_ptr() as usize,
                0,
            ],
        )
    })?;

    statuses
        .into_iter()
        .map(|status| match decode_nonnegative(status as isize) {
            Ok(node) if node < NODE_BITS => Ok(Ok(node as u16)),
            Err(SyscallError::Kernel(errno)) => Ok(Err(errno)),
            _ => Err(SyscallError::UnexpectedReturn(status as isize)),
        })
        .collect()
}

/// Migrates pages of the current process between nonempty node masks from
/// its allowed cpuset, returning the number of pages Linux could not move.
pub fn migrate_pages(from: &NumaNodeMask, to: &NumaNodeMask) -> Result<usize, SyscallError> {
    if from.is_empty() || to.is_empty() {
        return Err(SyscallError::InvalidInput(
            "source and destination NUMA masks must be nonempty",
        ));
    }
    let allowed = get_mempolicy_allowed()?;
    if !from.is_subset_of(&allowed) || !to.is_subset_of(&allowed) {
        return Err(SyscallError::InvalidInput(
            "source and destination NUMA masks must contain only allowed nodes",
        ));
    }
    decode_nonnegative(unsafe {
        abi::call(
            MIGRATE_PAGES,
            [
                0,
                MAXNODE,
                from.0.as_ptr() as usize,
                to.0.as_ptr() as usize,
                0,
                0,
            ],
        )
    })
}

/// Updates the home node of an existing bind policy over the full mapping.
/// Linux can reject a missing or incompatible policy.
pub fn set_mempolicy_home_node(mapping: &mut Mapping, node: u16) -> Result<(), SyscallError> {
    if usize::from(node) >= NODE_BITS {
        return Err(SyscallError::InvalidInput("NUMA node index exceeds 1023"));
    }
    let region = mapping.as_slice();
    if region.is_empty() {
        return Err(SyscallError::InvalidInput("mapping has no live region"));
    }
    decode_zero(unsafe {
        abi::call(
            SET_MEMPOLICY_HOME_NODE,
            [
                region.as_ptr() as usize,
                region.len(),
                usize::from(node),
                0,
                0,
                0,
            ],
        )
    })
}
