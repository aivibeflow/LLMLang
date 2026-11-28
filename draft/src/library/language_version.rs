//! Package language definitions and the append-only component registry.

use super::{invalid, Manifest, Result};
use sha2::{Digest, Sha256};

pub const LANGUAGE_VERSION: &str = "0.1.0.0.0";

const COMPONENTS: &[&str] = &[
    "syntax",
    "core_semantics",
    "type_system",
    "effects_execution",
    "modules_packages",
];

pub fn language_component_registry_digest() -> String {
    let mut digest = Sha256::new();
    digest.update(b"LLMLANG\0language-component-registry\0");
    for component in COMPONENTS {
        digest.update((component.len() as u32).to_be_bytes());
        digest.update(component.as_bytes());
    }
    format!("sha256:{:x}", digest.finalize())
}

pub(crate) fn check_manifest(manifest: &Manifest, supported_versions: &[&str]) -> Result<()> {
    if manifest.language_component_registry_digest != language_component_registry_digest() {
        return Err(invalid("unknown language component registry digest"));
    }
    let parts: Vec<_> = manifest.language_version.split('.').collect();
    if parts.len() != COMPONENTS.len()
        || parts.iter().any(|part| {
            part.is_empty()
                || (part.len() > 1 && part.starts_with('0'))
                || !part.bytes().all(|byte| byte.is_ascii_digit())
        })
    {
        return Err(invalid("invalid manifest language_version"));
    }
    if manifest.language_version != LANGUAGE_VERSION
        || !supported_versions.contains(&manifest.language_version.as_str())
    {
        return Err(invalid(format!(
            "unsupported language_version {}",
            manifest.language_version
        )));
    }
    Ok(())
}
