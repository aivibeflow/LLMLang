//! Local, single-principal LLMLang package authoring service.

mod changes;
mod native;
mod obligations;
mod scalar_source;
mod upgrade;
mod verification_report;

use changes::Selection;
use fs2::FileExt;
use llmlang_spg::{Graph, LoadOptions, Manifest, Package, SaveOptions, Tables};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Write};
use std::os::unix::fs::{DirBuilderExt, MetadataExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const VERSIONS: &[&str] = &["0.1.0"];
const BUILTIN: &str = "builtin";
type Result<T> = std::result::Result<T, ServerError>;

#[derive(Debug)]
pub struct ServerError {
    pub code: &'static str,
    pub message: String,
    pub verification: Option<Box<Value>>,
}

impl ServerError {
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            verification: None,
        }
    }

    fn with_verification(mut self, verification: Value) -> Self {
        self.verification = Some(Box::new(verification));
        self
    }
}

impl fmt::Display for ServerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for ServerError {}

impl From<io::Error> for ServerError {
    fn from(error: io::Error) -> Self {
        Self::new("IoError", error.to_string())
    }
}

impl From<serde_json::Error> for ServerError {
    fn from(error: serde_json::Error) -> Self {
        Self::new("InvalidArguments", error.to_string())
    }
}

fn invalid(message: impl Into<String>) -> ServerError {
    ServerError::new("InvalidArguments", message)
}
fn conflict(message: impl Into<String>) -> ServerError {
    ServerError::new("Conflict", message)
}
fn missing(message: impl Into<String>) -> ServerError {
    ServerError::new("MissingReference", message)
}
fn validation(error: impl fmt::Display) -> ServerError {
    ServerError::new("ValidationFailed", error.to_string())
}

#[derive(Clone, Serialize, Deserialize)]
struct Program {
    name: String,
    selection: Selection,
    manifest: Manifest,
    tables: Tables,
}

impl Program {
    fn package(&self) -> Package {
        Package {
            manifest: self.manifest.clone(),
            tables: self.tables.clone(),
        }
    }
}

#[derive(Clone, Serialize, Deserialize)]
struct Workspace {
    base_snapshot: String,
    revision: u64,
    committed: Option<String>,
    program: Program,
    requests: BTreeMap<String, Receipt>,
    reports: BTreeMap<u64, Value>,
}

#[derive(Clone, Serialize, Deserialize)]
struct Receipt {
    digest: String,
    principal_uid: u32,
    operations: Value,
    result: Value,
}

#[derive(Clone, Default, Serialize, Deserialize)]
struct State {
    sequence: u64,
    snapshots: BTreeMap<String, Program>,
    workspaces: BTreeMap<String, Workspace>,
}

impl State {
    fn retain_native(&mut self) {
        self.snapshots
            .retain(|_, program| native::is_native(&program.tables));
        self.workspaces
            .retain(|_, workspace| native::is_native(&workspace.program.tables));
    }

    fn persisted(&self) -> Self {
        let mut state = self.clone();
        state.retain_native();
        state
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PackageMetadata {
    name: String,
    selection: Selection,
    snapshot_id: String,
}

#[derive(Serialize, Deserialize)]
struct PendingCommit {
    state: State,
    snapshot_id: String,
}

pub struct Server {
    root: PathBuf,
    python: String,
    backend: PathBuf,
    principal_uid: u32,
    state: State,
    _lock: File,
}

impl Server {
    /// Convert a private, disposable copy after the v6 server has released it.
    pub fn migrate_v6_copy(state_dir: &Path, python: &str, backend: &Path) -> Result<Value> {
        if !state_dir.is_dir()
            || state_dir.join("pending.json").try_exists()?
            || state_dir.join("pending-package").try_exists()?
        {
            return Err(conflict(
                "v6 state must be an offline copy with no pending commit",
            ));
        }
        let mut server = Self::open(state_dir, python, backend)?;
        upgrade::migrate(&mut server)
    }

    pub fn open(state_dir: &Path, python: &str, backend: &Path) -> Result<Self> {
        fs::DirBuilder::new()
            .recursive(true)
            .mode(0o700)
            .create(state_dir)?;
        let root = state_dir.canonicalize()?;
        let metadata = fs::metadata(&root)?;
        if metadata.permissions().mode() & 0o077 != 0 {
            return Err(ServerError::new(
                "AccessDenied",
                "state directory must be private to its owner",
            ));
        }
        let lock = OpenOptions::new()
            .create(true)
            .truncate(false)
            .write(true)
            .open(root.join("lock"))?;
        lock.try_lock_exclusive()
            .map_err(|_| conflict("state directory is already in use"))?;
        fs::create_dir_all(root.join("packages"))?;
        fs::create_dir_all(root.join("artifacts"))?;
        let mut server = Self {
            state: read_optional(&root.join("state.json"))?.unwrap_or_default(),
            root,
            python: python.into(),
            backend: backend.canonicalize()?,
            principal_uid: metadata.uid(),
            _lock: lock,
        };
        server.state.retain_native();
        check_state_layout(&server.state)?;
        server.recover()?;
        Ok(server)
    }

    pub fn call(&mut self, tool: &str, args: Value) -> Result<Value> {
        if self.root.join("pending.json").try_exists()? {
            self.recover()?;
        }
        match tool {
            "create_package" => {
                let args: Create = serde_json::from_value(args)?;
                safe_name(&args.name)?;
                if !VERSIONS.contains(&args.language_version.as_str()) || args.profile != "scalar" {
                    return Err(ServerError::new(
                        "UnsupportedProfile",
                        "expected scalar LLMLang 0.1.0",
                    ));
                }
                let package = Package::empty(Manifest {
                    language_version: args.language_version,
                    dependencies: BTreeMap::new(),
                });
                let program = Program {
                    name: args.name,
                    selection: Selection::default(),
                    manifest: package.manifest,
                    tables: package.tables,
                };
                let id = snapshot_id(&program)?;
                let mut next = self.state.clone();
                next.snapshots.insert(id.clone(), program);
                self.open_workspace(next, &id)
            }
            "open_workspace" => {
                let args: SnapshotInput = serde_json::from_value(args)?;
                self.open_workspace(self.state.clone(), &args.snapshot_id)
            }
            "inspect_workspace" => {
                let args: WorkspaceInput = serde_json::from_value(args)?;
                Ok(view(
                    &args.workspace_id,
                    self.workspace(&args.workspace_id)?,
                ))
            }
            "apply_change_set" => self.apply(serde_json::from_value(args)?),
            "verify_workspace" => {
                let args: RevisionInput = serde_json::from_value(args)?;
                let result = self.verify_revision(&args)?;
                let mut next = self.state.clone();
                next.workspaces
                    .get_mut(&args.workspace_id)
                    .unwrap()
                    .reports
                    .insert(args.expected_revision, result.clone());
                self.store(next)?;
                Ok(result)
            }
            "commit_workspace" => self.commit(serde_json::from_value(args)?),
            "import_package" => {
                let args: Import = serde_json::from_value(args)?;
                self.import(Path::new(&args.path))
            }
            "build_package" => self.build(serde_json::from_value(args)?),
            _ => Err(invalid("unknown tool")),
        }
    }

    fn workspace(&self, id: &str) -> Result<&Workspace> {
        self.state
            .workspaces
            .get(id)
            .ok_or_else(|| missing("unknown workspace"))
    }

    fn checked_workspace(&self, args: &RevisionInput) -> Result<&Workspace> {
        let workspace = self.workspace(&args.workspace_id)?;
        if workspace.revision != args.expected_revision {
            return Err(ServerError::new(
                "StaleRevision",
                format!("current revision is {}", workspace.revision),
            ));
        }
        if workspace.committed.is_some() {
            return Err(conflict("workspace already committed"));
        }
        Ok(workspace)
    }

    fn open_workspace(&mut self, mut next: State, id: &str) -> Result<Value> {
        let program = next
            .snapshots
            .get(id)
            .ok_or_else(|| missing("unknown snapshot"))?
            .clone();
        next.sequence = next
            .sequence
            .checked_add(1)
            .ok_or_else(|| conflict("workspace ID exhausted"))?;
        let workspace_id = format!("workspace-{}", next.sequence);
        let workspace = Workspace {
            base_snapshot: id.into(),
            revision: 0,
            committed: None,
            program,
            requests: BTreeMap::new(),
            reports: BTreeMap::new(),
        };
        let result = view(&workspace_id, &workspace);
        next.workspaces.insert(workspace_id, workspace);
        self.store(next)?;
        Ok(result)
    }

    fn apply(&mut self, args: ChangeInput) -> Result<Value> {
        if args.idempotency_key.is_empty() {
            return Err(invalid("idempotency_key is empty"));
        }
        let request = hash(&(args.expected_revision, &args.operations))?;
        let revision = RevisionInput {
            workspace_id: args.workspace_id,
            expected_revision: args.expected_revision,
        };
        let id = &revision.workspace_id;
        if let Some(receipt) = self.workspace(id)?.requests.get(&args.idempotency_key) {
            return if receipt.digest == request {
                Ok(receipt.result.clone())
            } else {
                Err(conflict(
                    "idempotency key already used for a different request",
                ))
            };
        }
        let mut workspace = self.checked_workspace(&revision)?.clone();
        let native_profile = native::is_native(&workspace.program.tables);
        let mut package = workspace.program.package();
        let changes = changes::apply(
            &mut package,
            &mut workspace.program.selection,
            args.operations.clone(),
        )?;
        workspace.program.manifest = package.manifest;
        workspace.program.tables = package.tables;
        self.validate_edit(&mut workspace.program, native_profile)?;
        workspace.revision = workspace
            .revision
            .checked_add(1)
            .ok_or_else(|| conflict("revision exhausted"))?;
        let mut result = view(id, &workspace);
        result["identities"] = json!(changes.identities);
        result["affected_functions"] = json!(changes.affected_functions);
        workspace.requests.insert(
            args.idempotency_key,
            Receipt {
                digest: request,
                principal_uid: self.principal_uid,
                operations: args.operations,
                result: result.clone(),
            },
        );
        let mut next = self.state.clone();
        next.workspaces.insert(id.clone(), workspace);
        self.store(next)?;
        Ok(result)
    }

    fn validate_edit(&self, program: &mut Program, native_profile: bool) -> Result<()> {
        let combined = self.combined_package(program)?;
        let mut candidate = program.package();
        let rows = if native_profile {
            if !native::is_native(&program.tables) {
                return Err(ServerError::new(
                    "UnsupportedProfile",
                    "a native Change Set must retain the native profile",
                ));
            }
            self.validate_native(program, &combined)?;
            self.native_call_rows(program, &combined, |_| true)?
        } else {
            obligations::rows(&combined, &obligations::from_ir(&candidate)?)?
        };
        obligations::replace(&mut candidate, rows);
        program.tables = candidate.tables;
        if native_profile {
            self.check_graph(&self.combined_package(program)?)?;
        } else {
            self.validate(program)?;
        }
        Ok(())
    }

    fn dependency<'a>(&'a self, name: &str, pin: &str) -> Result<(&'a String, &'a Program)> {
        self.state
            .snapshots
            .get_key_value(pin)
            .filter(|(_, candidate)| {
                candidate.name == name && candidate.selection.version.is_some()
            })
            .or_else(|| {
                self.state.snapshots.iter().find(|(_, candidate)| {
                    candidate.name == name && candidate.selection.version.as_deref() == Some(pin)
                })
            })
            .ok_or_else(|| {
                ServerError::new("MissingDependency", format!("unavailable {name} at {pin}"))
            })
    }

    fn dependency_packages<'a>(
        &'a self,
        program: &Program,
    ) -> Result<BTreeMap<String, &'a Program>> {
        let mut dependencies = BTreeMap::new();
        let mut queue: Vec<_> = program.manifest.dependencies.iter().collect();
        while let Some((name, pin)) = queue.pop() {
            let (id, dependency) = self.dependency(name, pin)?;
            if dependencies.contains_key(id) {
                continue;
            }
            if dependency.manifest.language_version != program.manifest.language_version {
                return Err(ServerError::new(
                    "UnsupportedProfile",
                    "dependency language version differs",
                ));
            }
            queue.extend(dependency.manifest.dependencies.iter());
            dependencies.insert(id.clone(), dependency);
        }
        Ok(dependencies)
    }

    fn combined_package(&self, program: &Program) -> Result<Package> {
        // Check the owner of each function while package rows are still separate.
        check_builtin_access(program)?;
        let mut package = program.package();
        let include_native_calls = native::is_native(&package.tables);
        for dependency in self.dependency_packages(program)?.values() {
            check_builtin_access(dependency)?;
            for (table, rows) in &dependency.tables {
                // Catalog selections are package-local. Dependencies supply pinned objects.
                if matches!(
                    table.as_str(),
                    "versions" | "bindings" | "structure_bindings" | "verification_runs"
                ) || (table == "verification_obligations" && !include_native_calls)
                {
                    continue;
                }
                for (key, row) in rows {
                    let stored = package
                        .tables
                        .get_mut(table)
                        .unwrap()
                        .entry(key.clone())
                        .or_insert_with(|| row.clone());
                    if stored != row {
                        return Err(conflict(format!(
                            "conflicting dependency row {table}/{key}"
                        )));
                    }
                }
            }
        }
        Ok(package)
    }

    fn validate(&self, program: &Program) -> Result<Package> {
        let package = self.combined_package(program)?;
        changes::check_identities(&program.package(), &program.selection, &package)?;
        self.check_graph(&package)?;
        Self::check_entry_point(program)?;
        self.backend("validate", program, &package)?;
        Ok(package)
    }

    fn check_entry_point(program: &Program) -> Result<()> {
        if let Some(entry) = &program.selection.entry_point {
            if !program.tables["functions"].contains_key(entry) {
                return Err(validation("entry point must select a local implementation"));
            }
        }
        Ok(())
    }

    fn check_graph(&self, package: &Package) -> Result<()> {
        let mut combined = package.clone();
        combined.manifest.dependencies.clear();
        Graph::from_package(&combined).map_err(validation)?;
        Ok(())
    }

    fn native_catalog(program: &Program) -> Result<native::Catalog> {
        let version = program
            .selection
            .version
            .as_deref()
            .ok_or_else(|| invalid("missing selected version"))?;
        let mut versions = program.tables["versions"]
            .values()
            .filter(|row| row["version"] == version);
        let version_hash = versions
            .next()
            .and_then(|row| row["version_hash"].as_str())
            .ok_or_else(|| validation("selected version is absent from the package"))?;
        if versions.next().is_some() {
            return Err(validation("ambiguous package version"));
        }
        let mut catalog = native::Catalog::new();
        for binding in program.tables["bindings"]
            .values()
            .filter(|row| row["version_hash"] == version_hash)
        {
            let interface_hash = binding["interface_hash"]
                .as_str()
                .ok_or_else(|| validation("missing interface identity"))?;
            let arch = binding["arch"]
                .as_str()
                .ok_or_else(|| validation("missing or invalid binding arch"))?;
            let os = binding["os"]
                .as_str()
                .ok_or_else(|| validation("missing or invalid binding os"))?;
            if !llmlang_spg::valid_binding_target(arch, os) {
                return Err(validation("unregistered binding architecture or OS target"));
            }
            let implementation = binding["impl_hash"]
                .as_str()
                .ok_or_else(|| validation("missing implementation identity"))?;
            let interface = program.tables["interfaces"]
                .get(interface_hash)
                .ok_or_else(|| validation("missing local interface"))?;
            let name = interface["name"]
                .as_str()
                .ok_or_else(|| validation("missing interface name"))?;
            let contract = interface["public_contract_hash"]
                .as_str()
                .ok_or_else(|| validation("missing public contract pin"))?;
            if name.rsplit_once('.').map(|(namespace, _)| namespace) != Some(&program.name) {
                return Err(validation("export must belong to the package namespace"));
            }
            let entry =
                catalog
                    .entry(name.to_owned())
                    .or_insert_with(|| native::InterfaceBinding {
                        version: version.into(),
                        pin: native::InterfacePin {
                            name: name.into(),
                            version_hash: version_hash.into(),
                            interface_hash: interface_hash.into(),
                            required_contract_hash: contract.into(),
                        },
                        implementations: BTreeMap::new(),
                    });
            if entry.pin.interface_hash != interface_hash
                || entry
                    .implementations
                    .entry(arch.into())
                    .or_default()
                    .insert(os.into(), implementation.into())
                    .is_some()
            {
                return Err(validation("ambiguous public binding"));
            }
        }
        Ok(catalog)
    }

    fn native_catalogs(&self, program: &Program) -> Result<native::CallBindings> {
        let dependencies = self.dependency_packages(program)?;
        let mut bindings = BTreeMap::new();
        for candidate in std::iter::once(program).chain(dependencies.values().copied()) {
            let mut catalog = Self::native_catalog(candidate)?;
            for (name, version) in &candidate.manifest.dependencies {
                let (_, dependency) = self.dependency(name, version)?;
                for (name, binding) in Self::native_catalog(dependency)? {
                    if catalog.insert(name, binding).is_some() {
                        return Err(validation("ambiguous native dependency interface"));
                    }
                }
            }
            let catalog = std::sync::Arc::new(catalog);
            for implementation in candidate.tables["functions"].keys() {
                bindings
                    .entry(implementation.clone())
                    .or_insert_with(|| catalog.clone());
            }
        }
        Ok(bindings)
    }

    fn validate_native(&self, program: &Program, package: &Package) -> Result<()> {
        self.check_graph(package)?;
        Self::check_entry_point(program)?;
        let local = program.package();
        for (version, row) in &local.tables["versions"] {
            if row["binding_hash"] != changes::binding_identity(&local, version)? {
                return Err(validation("invalid version binding hash"));
            }
        }
        for binding in local.tables["bindings"].values() {
            let interface = local.tables["interfaces"]
                .get(binding["interface_hash"].as_str().unwrap())
                .ok_or_else(|| validation("missing local interface"))?;
            let function = &package.tables["functions"][binding["impl_hash"].as_str().unwrap()];
            let contract = interface["public_contract_hash"]
                .as_str()
                .ok_or_else(|| validation("missing local public contract pin"))?;
            if function["provided_contract_hash"] != contract
                || package.tables["contracts"][contract]["typed_signature"]
                    != package
                        .function_signature(function)
                        .map_err(validation)?
                        .typed
            {
                return Err(validation(
                    "native export contract and implementation must have the exact signature",
                ));
            }
            if (binding["arch"] == "" || binding["os"] == "")
                && native::requires_platform(&program.name, function)?
            {
                return Err(validation(
                    "platform-specific native implementation requires both an architecture and an OS",
                ));
            }
        }
        Ok(())
    }

    fn native_output(
        &self,
        program: &Program,
        package: &mut Package,
        target: native::Target<'_>,
    ) -> Result<native::Output> {
        let exports = Self::native_catalog(program)?
            .into_iter()
            .map(|(name, binding)| Ok((name, binding.select(target)?.1.into())))
            .collect::<Result<_>>()?;
        let output = native::lower(
            &program.name,
            package,
            &exports,
            &self.native_catalogs(program)?,
            target,
        )?;
        // Keep the selected call graph in the build's transient SPG.
        let rows = obligations::rows(package, &output.calls)?;
        obligations::replace(package, rows);
        self.check_graph(package)?;
        Ok(output)
    }

    fn validate_native_sources(&self, program: &Program, package: &Package) -> Result<()> {
        let actual: BTreeMap<_, _> = program.tables["verification_obligations"]
            .iter()
            .filter(|(_, row)| row["kind"] == "call_compatibility")
            .map(|(key, row)| (key.clone(), row.clone()))
            .collect();
        let callers: BTreeSet<_> = actual
            .values()
            .filter_map(|row| row["caller_impl_hash"].as_str())
            .collect();
        if self.native_call_rows(program, package, |caller| callers.contains(caller))? != actual {
            return Err(validation(
                "native call obligations disagree with the resolved source",
            ));
        }
        Ok(())
    }

    fn native_call_rows(
        &self,
        program: &Program,
        package: &Package,
        resolve: impl Fn(&str) -> bool,
    ) -> Result<BTreeMap<String, Value>> {
        let catalogs = self.native_catalogs(program)?;
        let mut calls = obligations::CallsByCaller::new();
        for (implementation, row) in &program.tables["functions"] {
            if native::implementation_identity(
                &program.name,
                package,
                row,
                &catalogs[implementation],
            )? != *implementation
            {
                return Err(validation("native source or interface identity mismatch"));
            }
            if resolve(implementation) {
                calls.insert(
                    implementation.clone(),
                    native::resolved_calls(
                        &program.name,
                        package,
                        row,
                        &catalogs,
                        native::LINUX_X86_64,
                    )?,
                );
            }
        }
        obligations::rows(package, &calls)
    }

    fn backend(&self, action: &str, program: &Program, package: &Package) -> Result<Value> {
        let version_hash = program.tables["versions"]
            .values()
            .find(|row| row["version"].as_str() == program.selection.version.as_deref())
            .and_then(|row| row["version_hash"].as_str());
        // The scalar frontend consumes its typed view. The repository rows
        // remain normalized and the view is local to this backend request.
        let mut tables = package.tables.clone();
        for row in tables.get_mut("functions").unwrap().values_mut() {
            let body = scalar_source::body(package, row)?;
            if let std::borrow::Cow::Owned(body) = body {
                row["canonical_body"] = body;
            }
            row["typed_signature"] = package.function_signature(row).map_err(validation)?.typed;
        }
        let request = json!({
            "action": action,
            "package": {"manifest": package.manifest, "tables": tables},
            "entry_impl_hash": program.selection.entry_point,
            "version_hash": version_hash,
        });
        let input = serde_json::to_vec(&request)?;
        let mut child = Command::new(&self.python)
            .arg(&self.backend)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;
        let write = child.stdin.take().unwrap().write_all(&input);
        let output = child.wait_with_output()?;
        write?;
        if !output.status.success() {
            return Err(ServerError::new(
                "ToolError",
                String::from_utf8_lossy(&output.stderr).trim(),
            ));
        }
        let reply: Value = serde_json::from_slice(&output.stdout)
            .map_err(|error| ServerError::new("ToolError", error.to_string()))?;
        if reply["ok"] != true && !(action == "verify" && reply["report"].is_object()) {
            let code = match reply["code"].as_str() {
                Some("UnsupportedProfile") => "UnsupportedProfile",
                Some("ToolError") => "ToolError",
                _ if action == "verify" => "VerificationFailed",
                _ => "ValidationFailed",
            };
            return Err(ServerError::new(
                code,
                reply["message"]
                    .as_str()
                    .unwrap_or("scalar backend rejected the request"),
            ));
        }
        Ok(reply)
    }

    fn verify_revision(&self, args: &RevisionInput) -> Result<Value> {
        let program = &self.checked_workspace(args)?.program;
        if native::is_native(&program.tables) {
            return Err(ServerError::new(
                "UnsupportedProfile",
                "contract verification is unavailable for native workspaces",
            ));
        }
        let package = self.validate(program)?;
        let report = self.backend("verify", program, &package)?;
        let failures = verification_report::failures(&package, &report["report"])?;
        Ok(json!({
            "workspace_id": args.workspace_id,
            "revision": args.expected_revision,
            "report": report,
            "failures": failures,
        }))
    }

    fn commit(&mut self, args: RevisionInput) -> Result<Value> {
        let workspace = self.checked_workspace(&args)?.clone();
        let program = &workspace.program;
        let version = program
            .selection
            .version
            .as_deref()
            .ok_or_else(|| invalid("select a package version first"))?;
        safe_name(version)?;
        if program.tables["bindings"].is_empty() && program.selection.entry_point.is_none() {
            return Err(validation("package must select an export or entry point"));
        }
        let id = snapshot_id(program)?;
        self.check_version(program, &id)?;
        let verification = self.verify_revision(&args)?;
        let report = &verification["report"];
        if report["ok"] != true || report["report"]["status"] != "VERIFIED" {
            return Err(ServerError::new(
                "VerificationFailed",
                report["message"]
                    .as_str()
                    .unwrap_or("required verification failed"),
            )
            .with_verification(verification));
        }
        if !native::is_native(&program.tables) {
            return Err(ServerError::new(
                "UnsupportedProfile",
                "verified scalar workspaces cannot be published",
            )
            .with_verification(verification));
        }
        self.checked_workspace(&args)?;
        let path = self.package_path(program)?;
        if path.exists() {
            return Err(conflict("package destination already exists"));
        }

        let staged = self.root.join("pending-package");
        llmlang_spg::save(
            &staged,
            &program.package(),
            SaveOptions {
                write_text_dump: true,
            },
        )
        .map_err(validation)?;
        let metadata = PackageMetadata {
            name: program.name.clone(),
            selection: program.selection.clone(),
            snapshot_id: id.clone(),
        };
        if let Err(error) = write_atomic(&staged.join("package.json"), &metadata) {
            fs::remove_dir_all(&staged)?;
            return Err(error);
        }
        let mut next = self.state.clone();
        let revised = next.workspaces.get_mut(&args.workspace_id).unwrap();
        revised.committed = Some(id.clone());
        revised.reports.insert(args.expected_revision, verification);
        next.snapshots.insert(id.clone(), program.clone());
        let pending = PendingCommit {
            state: next.persisted(),
            snapshot_id: id.clone(),
        };
        if let Err(error) = write_atomic(&self.root.join("pending.json"), &pending) {
            fs::remove_dir_all(staged)?;
            return Err(error);
        }
        if let Err(error) = publish_new(&staged, &path) {
            self.clear_pending()?;
            return Err(error);
        }
        if let Err(error) = write_atomic(&self.root.join("state.json"), &pending.state) {
            // The journal remains available if restoring the previous generation fails.
            fs::rename(&path, &staged)?;
            self.clear_pending()?;
            return Err(error);
        }
        self.state = next;
        // A stale journal is safe to replay after state and package publication.
        let _ = fs::remove_file(self.root.join("pending.json"));
        Ok(json!({"snapshot_id": id, "package_path": path, "revision": args.expected_revision}))
    }

    fn package_path(&self, program: &Program) -> Result<PathBuf> {
        let version = program
            .selection
            .version
            .as_deref()
            .ok_or_else(|| invalid("package version is required"))?;
        safe_name(&program.name)?;
        safe_name(version)?;
        Ok(self.root.join("packages").join(&program.name).join(version))
    }

    fn check_version(&self, program: &Program, id: &str) -> Result<()> {
        if self.state.snapshots.iter().any(|(old_id, old)| {
            old_id != id
                && old.name == program.name
                && old.selection.version == program.selection.version
        }) {
            return Err(conflict(
                "package version already identifies another snapshot",
            ));
        }
        Ok(())
    }

    fn import(&mut self, path: &Path) -> Result<Value> {
        let metadata: PackageMetadata = read_json(&path.join("package.json"))?;
        let package =
            llmlang_spg::load(path, VERSIONS, LoadOptions::default()).map_err(validation)?;
        let program = Program {
            name: metadata.name,
            selection: metadata.selection,
            manifest: package.manifest,
            tables: package.tables,
        };
        self.package_path(&program)?;
        let id = snapshot_id(&program)?;
        if metadata.snapshot_id != id {
            return Err(validation("package snapshot identity mismatch"));
        }
        self.check_version(&program, &id)?;
        if !native::is_native(&program.tables) {
            return Err(ServerError::new(
                "UnsupportedProfile",
                "only native source packages can be imported",
            ));
        }
        let package = self.combined_package(&program)?;
        self.validate_native(&program, &package)?;
        self.validate_native_sources(&program, &package)?;
        let mut next = self.state.clone();
        let versions: BTreeSet<_> = next
            .snapshots
            .values()
            .filter(|old| old.name == program.name)
            .filter_map(|old| old.selection.version.clone())
            .chain(program.selection.version.clone())
            .collect();
        next.snapshots.insert(id.clone(), program);
        self.store(next)?;
        Ok(json!({"snapshot_id": id, "versions": versions,
            "verification_status": "unchecked"}))
    }

    fn build(&self, args: Build) -> Result<Value> {
        let program = self
            .state
            .snapshots
            .get(&args.snapshot_id)
            .filter(|program| program.selection.version.is_some())
            .ok_or_else(|| missing("unknown committed snapshot"))?;
        let target = match args.target.as_str() {
            "linux-x86_64" => native::LINUX_X86_64,
            _ => {
                return Err(ServerError::new(
                    "UnsupportedProfile",
                    "expected linux-x86_64",
                ))
            }
        };
        let area = tempfile::tempdir_in(self.root.join("artifacts"))?;
        let staged = area.path().join("program");
        if !native::is_native(&program.tables) {
            return Err(ServerError::new(
                "UnsupportedProfile",
                "only native source packages can be built",
            ));
        }
        let mut package = self.combined_package(program)?;
        self.validate_native(program, &package)?;
        self.validate_native_sources(program, &package)?;
        let output = self.native_output(program, &mut package, target)?;
        native::compile(&output, &staged)?;
        let (executable, exports) = (output.executable, output.exports);
        if !staged.is_file() {
            return Err(ServerError::new(
                "ToolError",
                "backend did not create the artifact",
            ));
        }
        let name = if executable {
            format!("{}-{}", args.snapshot_id, args.target)
        } else {
            format!("libllmlang_{}.rlib", args.snapshot_id)
        };
        let artifact = self.root.join("artifacts").join(&name);
        let mut response = json!({"snapshot_id": args.snapshot_id, "target": args.target,
            "artifact": artifact, "exports": exports, "verification_status": "unchecked"});
        if executable {
            let debug = native::split_debug(&staged, &name)?;
            let destination = artifact.with_file_name(debug.file_name().unwrap());
            // Publish the content-addressed companion first so a previous build keeps its debug link.
            fs::rename(debug, &destination)?;
            response["debug_artifact"] = json!(destination);
        }
        fs::rename(staged, &artifact)?;
        Ok(response)
    }

    fn store(&mut self, state: State) -> Result<()> {
        write_atomic(&self.root.join("state.json"), &state.persisted())?;
        self.state = state;
        Ok(())
    }

    fn recover(&mut self) -> Result<()> {
        if let Some(pending) = read_optional::<PendingCommit>(&self.root.join("pending.json"))? {
            check_state_layout(&pending.state)?;
            let program = pending
                .state
                .snapshots
                .get(&pending.snapshot_id)
                .ok_or_else(|| validation("journal snapshot missing"))?;
            let path = self.package_path(program)?;
            if path.exists() && !self.root.join("pending-package").exists() {
                let metadata: PackageMetadata = read_json(&path.join("package.json"))?;
                if metadata.snapshot_id != pending.snapshot_id {
                    return Err(conflict(
                        "pending package publication conflicts with destination",
                    ));
                }
                let package = llmlang_spg::load(&path, VERSIONS, LoadOptions::default())
                    .map_err(validation)?;
                if package != program.package() {
                    return Err(validation("pending package differs from journal"));
                }
                let mut recovered = pending.state;
                for (key, program) in &self.state.snapshots {
                    if !native::is_native(&program.tables) {
                        recovered.snapshots.insert(key.clone(), program.clone());
                    }
                }
                for (key, workspace) in &self.state.workspaces {
                    if !native::is_native(&workspace.program.tables) {
                        recovered.workspaces.insert(key.clone(), workspace.clone());
                    }
                }
                recovered.sequence = recovered.sequence.max(self.state.sequence);
                self.store(recovered)?;
            }
        }
        self.clear_pending()
    }

    fn clear_pending(&self) -> Result<()> {
        let staged = self.root.join("pending-package");
        if staged.exists() {
            fs::remove_dir_all(staged)?;
        }
        let journal = self.root.join("pending.json");
        if journal.exists() {
            fs::remove_file(journal)?;
        }
        Ok(())
    }

    pub fn read_resource(&self, uri: &str) -> Result<Value> {
        let path = uri
            .strip_prefix("llmlang://")
            .ok_or_else(|| invalid("unsupported resource URI"))?;
        let parts = path
            .split('/')
            .map(decode_segment)
            .collect::<Result<Vec<_>>>()?;
        let segments: Vec<_> = parts.iter().map(String::as_str).collect();
        match segments.as_slice() {
            ["workspace", id] => Ok(view(id, self.workspace(id)?)),
            ["workspace", id, "verification", revision] => {
                let revision = revision.parse().map_err(|_| invalid("invalid revision"))?;
                self.workspace(id)?
                    .reports
                    .get(&revision)
                    .cloned()
                    .ok_or_else(|| missing("verification report is unavailable"))
            }
            ["workspace", id, "object", table, key] => {
                let program = &self.workspace(id)?.program;
                self.object_resource(program, "workspace", id, table, key)
            }
            ["snapshot", id, "object", table, key] => {
                let program = self
                    .state
                    .snapshots
                    .get(*id)
                    .ok_or_else(|| missing("unknown snapshot"))?;
                self.object_resource(program, "snapshot", id, table, key)
            }
            _ => Err(invalid("unsupported resource URI")),
        }
    }

    fn object_resource(
        &self,
        program: &Program,
        scope: &str,
        id: &str,
        table: &str,
        key: &str,
    ) -> Result<Value> {
        let mut package = self.combined_package(program)?;
        let dependencies = std::mem::take(&mut package.manifest.dependencies);
        let graph = Graph::from_package(&package).map_err(validation)?;
        package.manifest.dependencies = dependencies;
        let node = graph
            .objects()
            .find(|node| node.object().table == table && node.object().storage_key == key)
            .ok_or_else(|| missing("unknown object"))?;
        let link_to = |relation: &str, table: &str, key: &str| {
            json!({
                "relation": relation,
                "uri": format!("llmlang://{scope}/{id}/object/{table}/{}", encode_segment(key)),
            })
        };
        let link = |(relation, node): (_, llmlang_spg::Node<'_>)| {
            let object = node.object();
            link_to(&format!("{relation:?}"), object.table, &object.storage_key)
        };
        let mut outgoing = node.outgoing().map(link).collect::<Vec<_>>();
        let mut incoming = node.incoming().map(link).collect::<Vec<_>>();
        if matches!(table, "functions" | "contracts") {
            for row in package.tables["verification_obligations"]
                .values()
                .filter(|row| row["kind"] == "call_compatibility")
            {
                let caller = row["caller_impl_hash"].as_str().unwrap();
                let callee = row["callee_impl_hash"].as_str().unwrap();
                let contract = row["caller_required_contract_hash"].as_str().unwrap();
                if table == "functions" && caller == key {
                    for edge in [
                        link_to("Callee", "functions", callee),
                        link_to("RequiredContract", "contracts", contract),
                    ] {
                        if !outgoing.contains(&edge) {
                            outgoing.push(edge);
                        }
                    }
                }
                if (table == "functions" && callee == key)
                    || (table == "contracts" && contract == key)
                {
                    let relation = if table == "functions" {
                        "Callee"
                    } else {
                        "RequiredContract"
                    };
                    let edge = link_to(relation, "functions", caller);
                    if !incoming.contains(&edge) {
                        incoming.push(edge);
                    }
                }
            }
        }
        Ok(json!({
            "table": table, "key": key, "content_hash": node.object().content_hash,
            "row": package.tables[table][key],
            "outgoing": outgoing,
            "incoming": incoming,
        }))
    }
}

fn check_builtin_access(program: &Program) -> Result<()> {
    if program.name == BUILTIN {
        return Ok(());
    }
    for row in program.tables["functions"].values() {
        let body = &row["canonical_body"];
        let builtin = if let Some(source) = body.as_str() {
            native::referenced_builtin(source)?
        } else {
            scalar_uses_fail(body).then(|| "builtin__fail".into())
        };
        if let Some(builtin) = builtin {
            return Err(validation(format!(
                "{builtin} may only be used in package {BUILTIN} (found in package {})",
                program.name
            )));
        }
    }
    Ok(())
}

fn scalar_uses_fail(node: &Value) -> bool {
    match node {
        Value::Array(items) => {
            // `fail` is the canonical scalar lowering of `builtin__fail`.
            items.first().is_some_and(|tag| tag == "fail") || items.iter().any(scalar_uses_fail)
        }
        Value::Object(fields) => fields.values().any(scalar_uses_fail),
        _ => false,
    }
}

fn check_state_layout(state: &State) -> Result<()> {
    let programs = state.snapshots.values().chain(
        state
            .workspaces
            .values()
            .map(|workspace| &workspace.program),
    );
    for program in programs {
        if !program
            .tables
            .keys()
            .map(String::as_str)
            .eq(llmlang_spg::TABLES)
        {
            return Err(ServerError::new(
                "UnsupportedProfile",
                "server state uses another package table layout",
            ));
        }
    }
    Ok(())
}

fn view(id: &str, workspace: &Workspace) -> Value {
    let program = &workspace.program;
    let exports: Vec<_> = program.tables["bindings"].values().filter_map(|binding| {
        let interface_hash = binding["interface_hash"].as_str()?;
        let interface = program.tables["interfaces"].get(interface_hash)?;
        Some(json!({"name":interface["name"],"interface_hash":interface_hash,"impl_hash":binding["impl_hash"],"arch":binding["arch"],"os":binding["os"]}))
    }).collect();
    json!({
        "workspace_id": id,
        "base_snapshot": workspace.base_snapshot,
        "revision": workspace.revision,
        "state": if workspace.committed.is_some() { "committed" } else { "open" },
        "snapshot_id": workspace.committed,
        "package": program.name,
        "version": program.selection.version,
        "manifest": program.manifest,
        "exports": exports,
        "entry_point": program.selection.entry_point,
        "resource_uri": format!("llmlang://workspace/{id}"),
    })
}

fn decode_segment(segment: &str) -> Result<String> {
    let mut bytes = segment.bytes();
    let mut out = Vec::new();
    while let Some(byte) = bytes.next() {
        if byte != b'%' {
            out.push(byte);
            continue;
        }
        let mut digit = || {
            bytes
                .next()
                .and_then(|b| (b as char).to_digit(16))
                .ok_or_else(|| invalid("bad percent encoding in resource URI"))
        };
        out.push((digit()? * 16 + digit()?) as u8);
    }
    String::from_utf8(out).map_err(|_| invalid("invalid UTF-8 in resource URI"))
}

fn encode_segment(value: &str) -> String {
    let mut result = String::new();
    for byte in value.bytes() {
        if byte.is_ascii_alphanumeric() || b"-._~".contains(&byte) {
            result.push(byte as char);
        } else {
            use std::fmt::Write as _;
            write!(result, "%{byte:02X}").unwrap();
        }
    }
    result
}

fn safe_name(value: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 128
        || value == "."
        || value == ".."
        || !value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"._-".contains(&b))
    {
        return Err(invalid(
            "package names and versions must be safe path components",
        ));
    }
    Ok(())
}

fn hash(value: &impl Serialize) -> Result<String> {
    Ok(format!("{:x}", Sha256::digest(serde_json::to_vec(value)?)))
}

fn snapshot_id(program: &Program) -> Result<String> {
    hash(&("llmlang-server-snapshot/v1", program))
}

fn read_json<T: DeserializeOwned>(path: &Path) -> Result<T> {
    Ok(serde_json::from_reader(File::open(path)?)?)
}

fn read_optional<T: DeserializeOwned>(path: &Path) -> Result<Option<T>> {
    match File::open(path) {
        Ok(input) => Ok(Some(serde_json::from_reader(input)?)),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error.into()),
    }
}

fn write_atomic(path: &Path, value: &impl Serialize) -> Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| invalid("missing parent directory"))?;
    let mut temp = tempfile::NamedTempFile::new_in(parent)?;
    serde_json::to_writer(&mut temp, value)?;
    temp.write_all(b"\n")?;
    temp.as_file().sync_all()?;
    temp.persist(path).map_err(|error| error.error)?;
    Ok(())
}

fn publish_new(staged: &Path, destination: &Path) -> Result<()> {
    let parent = destination
        .parent()
        .ok_or_else(|| invalid("missing package parent"))?;
    fs::create_dir_all(parent)?;
    if let Err(error) = rustix::fs::renameat_with(
        rustix::fs::CWD,
        staged,
        rustix::fs::CWD,
        destination,
        rustix::fs::RenameFlags::NOREPLACE,
    ) {
        if error == rustix::io::Errno::EXIST {
            return Err(conflict("package destination already exists"));
        }
        return Err(io::Error::from(error).into());
    }
    Ok(())
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Create {
    name: String,
    profile: String,
    language_version: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Import {
    path: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SnapshotInput {
    snapshot_id: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct WorkspaceInput {
    workspace_id: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RevisionInput {
    workspace_id: String,
    expected_revision: u64,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ChangeInput {
    workspace_id: String,
    expected_revision: u64,
    idempotency_key: String,
    operations: Value,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Build {
    snapshot_id: String,
    target: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_build_resolves_the_same_caller_for_each_platform() {
        let directory = tempfile::tempdir().unwrap();
        let draft = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let mut server =
            Server::open(directory.path(), "python3", &draft.join("server/scalar.py")).unwrap();
        let builtin_id = server.import(&draft.join("builtin")).unwrap()["snapshot_id"]
            .as_str()
            .unwrap()
            .to_owned();
        let hello_id = server
            .import(&draft.join("examples/0001-hello-world"))
            .unwrap()["snapshot_id"]
            .as_str()
            .unwrap()
            .to_owned();
        let program = server.state.snapshots[&hello_id].clone();
        let builtin = server.state.snapshots.get_mut(&builtin_id).unwrap();
        let catalog = Server::native_catalog(builtin).unwrap();
        let write = &catalog["builtin.write"];
        let portable = write.implementations[""][""].clone();
        let mut function = builtin.tables["functions"][&portable].clone();
        function["canonical_body"] = json!("{ builtin__write_utf8(-1, utf8) }");
        let exact =
            native::implementation_identity(BUILTIN, &builtin.package(), &function, &catalog)
                .unwrap();
        function["impl_hash"] = json!(exact);
        builtin
            .tables
            .get_mut("functions")
            .unwrap()
            .insert(exact.clone(), function);
        let portable_key = format!("{}:{}::", write.pin.version_hash, write.pin.interface_hash);
        let mut binding = builtin.tables["bindings"][&portable_key].clone();
        binding["arch"] = json!(native::LINUX_X86_64.0);
        binding["os"] = json!(native::LINUX_X86_64.1);
        binding["impl_hash"] = json!(exact);
        builtin.tables.get_mut("bindings").unwrap().insert(
            format!(
                "{}:{}:x86_64:linux",
                write.pin.version_hash, write.pin.interface_hash
            ),
            binding,
        );

        let caller = program.tables["functions"].keys().next().unwrap();
        let mut package = server.combined_package(&program).unwrap();
        let selected = server
            .native_output(&program, &mut package, native::LINUX_X86_64)
            .unwrap();
        assert_eq!(
            selected.calls[caller].first().unwrap().callee_impl_hash,
            exact
        );
        let exact_rows = package.tables["verification_obligations"].clone();

        let portable_target = ("aarch64", "linux");
        let mut package = server.combined_package(&program).unwrap();
        let selected = server
            .native_output(&program, &mut package, portable_target)
            .unwrap();
        assert_eq!(
            selected.calls[caller].first().unwrap().callee_impl_hash,
            portable
        );
        assert_ne!(exact_rows, package.tables["verification_obligations"]);

        server
            .state
            .snapshots
            .get_mut(&builtin_id)
            .unwrap()
            .tables
            .get_mut("bindings")
            .unwrap()
            .remove(&portable_key);
        let mut package = server.combined_package(&program).unwrap();
        let Err(error) = server.native_output(&program, &mut package, portable_target) else {
            panic!("a missing target binding was accepted");
        };
        assert_eq!(error.code, "MissingImplementation");
        assert!(error
            .message
            .contains("builtin.write at version 0.1.0 has no binding for (aarch64, linux)"));
    }

    #[test]
    fn checks_native_builtin_access_at_import_and_build() {
        let directory = tempfile::tempdir().unwrap();
        let server_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
        let mut server =
            Server::open(directory.path(), "python3", &server_dir.join("scalar.py")).unwrap();
        let package = llmlang_spg::load(
            &server_dir.join("../builtin"),
            VERSIONS,
            LoadOptions::default(),
        )
        .unwrap();
        let legacy = Program {
            name: "stdlib".into(),
            selection: Selection {
                version: Some("0.1.0".into()),
                entry_point: None,
            },
            manifest: package.manifest.clone(),
            tables: package.tables.clone(),
        };
        let id = snapshot_id(&legacy).unwrap();
        let path = directory.path().join("legacy-package");
        llmlang_spg::save(&path, &package, SaveOptions::default()).unwrap();
        write_atomic(
            &path.join("package.json"),
            &PackageMetadata {
                name: legacy.name.clone(),
                selection: legacy.selection.clone(),
                snapshot_id: id.clone(),
            },
        )
        .unwrap();
        let error = server
            .call("import_package", json!({"path": path}))
            .unwrap_err();
        assert_eq!(error.code, "ValidationFailed");
        assert!(error.message.starts_with("builtin__"));
        assert!(error.message.ends_with("(found in package stdlib)"));
        assert!(!server.state.snapshots.contains_key(&id));

        // Simulate a snapshot persisted before the ownership check was added.
        server.state.snapshots.insert(id.clone(), legacy.clone());
        let build_error = server
            .call(
                "build_package",
                json!({
                    "snapshot_id": id,
                    "target": "linux-x86_64",
                }),
            )
            .unwrap_err();
        assert_eq!(build_error.code, error.code);
        assert_eq!(build_error.message, error.message);
        assert!(fs::read_dir(server.root.join("artifacts"))
            .unwrap()
            .next()
            .is_none());

        let mut builtin = Program {
            name: BUILTIN.into(),
            ..legacy
        };
        assert!(server.combined_package(&builtin).is_ok());
        builtin.manifest.dependencies.insert("stdlib".into(), id);
        let dependency_error = server.combined_package(&builtin).unwrap_err();
        assert_eq!(dependency_error.code, error.code);
        assert_eq!(dependency_error.message, error.message);
    }

    #[test]
    fn recovers_published_package_after_interruption() {
        let directory = tempfile::tempdir().unwrap();
        let backend = Path::new(env!("CARGO_MANIFEST_DIR")).join("scalar.py");
        let server = Server::open(directory.path(), "python3", &backend).unwrap();

        let package = llmlang_spg::load(
            &Path::new(env!("CARGO_MANIFEST_DIR")).join("../builtin"),
            VERSIONS,
            LoadOptions::default(),
        )
        .unwrap();
        let program = Program {
            name: "recovery".into(),
            selection: Selection {
                version: Some("1".into()),
                entry_point: None,
            },
            manifest: package.manifest.clone(),
            tables: package.tables.clone(),
        };
        let id = snapshot_id(&program).unwrap();
        let destination = server.package_path(&program).unwrap();
        let staged = server.root.join("pending-package");
        llmlang_spg::save(&staged, &package, SaveOptions::default()).unwrap();
        write_atomic(
            &staged.join("package.json"),
            &PackageMetadata {
                name: program.name.clone(),
                selection: program.selection.clone(),
                snapshot_id: id.clone(),
            },
        )
        .unwrap();
        let mut successor = server.state.clone();
        successor.snapshots.insert(id.clone(), program);
        write_atomic(
            &server.root.join("pending.json"),
            &PendingCommit {
                state: successor,
                snapshot_id: id.clone(),
            },
        )
        .unwrap();
        publish_new(&staged, &destination).unwrap();
        drop(server);

        let server = Server::open(directory.path(), "python3", &backend).unwrap();
        assert!(server.state.snapshots.contains_key(&id));
        assert!(destination.is_dir());
        assert!(!server.root.join("pending.json").exists());
    }

    #[test]
    fn rejects_shared_state_directory() {
        let directory = tempfile::tempdir().unwrap();
        fs::set_permissions(directory.path(), fs::Permissions::from_mode(0o755)).unwrap();
        let backend = Path::new(env!("CARGO_MANIFEST_DIR")).join("scalar.py");
        let error = Server::open(directory.path(), "python3", &backend)
            .err()
            .unwrap();
        assert_eq!(error.code, "AccessDenied");
    }
}
