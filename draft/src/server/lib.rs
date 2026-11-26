//! Local, single-principal LLMLang package authoring service.

mod changes;

use changes::Selection;
use fs2::FileExt;
use llmlang_spg::{Graph, GraphLoadOptions, LoadOptions, Manifest, Package, SaveOptions, Tables};
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
type Result<T> = std::result::Result<T, ServerError>;

#[derive(Debug)]
pub struct ServerError {
    pub code: &'static str,
    pub message: String,
}

impl ServerError {
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
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
                let workspace = self.checked_workspace(&args)?;
                let package = self.validate(&workspace.program)?;
                let report = self.backend("verify", &workspace.program, &package, None)?;
                let result = json!({"workspace_id": args.workspace_id, "revision": args.expected_revision, "report": report});
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
        let mut package = workspace.program.package();
        let changes = changes::apply(
            &mut package,
            &mut workspace.program.selection,
            args.operations.clone(),
        )?;
        workspace.program.manifest = package.manifest;
        workspace.program.tables = package.tables;
        self.validate(&workspace.program)?;
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

    fn dependency_packages<'a>(
        &'a self,
        program: &Program,
    ) -> Result<BTreeMap<String, &'a Program>> {
        let mut dependencies = BTreeMap::new();
        let mut queue: Vec<_> = program.manifest.dependencies.values().cloned().collect();
        while let Some(pin) = queue.pop() {
            if dependencies.contains_key(&pin) {
                continue;
            }
            let dependency = self
                .state
                .snapshots
                .get(&pin)
                .filter(|candidate| candidate.selection.version.is_some())
                .ok_or_else(|| {
                    ServerError::new("MissingDependency", format!("unavailable snapshot {pin}"))
                })?;
            if dependency.manifest.language_version != program.manifest.language_version {
                return Err(ServerError::new(
                    "UnsupportedProfile",
                    "dependency language version differs",
                ));
            }
            queue.extend(dependency.manifest.dependencies.values().cloned());
            dependencies.insert(pin, dependency);
        }
        Ok(dependencies)
    }

    fn combined_package(&self, program: &Program) -> Result<Package> {
        let mut package = program.package();
        for dependency in self.dependency_packages(program)?.values() {
            for (table, rows) in &dependency.tables {
                // Catalog selections are package-local. Dependencies supply pinned objects.
                if matches!(
                    table.as_str(),
                    "versions"
                        | "bindings"
                        | "structure_bindings"
                        | "verification_obligations"
                        | "verification_runs"
                ) {
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
        changes::check_identities(&program.package(), &program.selection)?;
        let package = self.combined_package(program)?;
        let mut combined = package.clone();
        combined.manifest.dependencies.clear();
        let area = tempfile::tempdir_in(&self.root)?;
        let path = area.path().join("candidate");
        llmlang_spg::save(&path, &combined, SaveOptions::default()).map_err(validation)?;
        llmlang_spg::load_graph(&path, VERSIONS, GraphLoadOptions::default())
            .map_err(validation)?;
        if let Some(entry) = &program.selection.entry_point {
            if !program.tables["functions"].contains_key(entry) {
                return Err(validation("entry point must select a local implementation"));
            }
        }
        self.backend("validate", program, &package, None)?;
        Ok(package)
    }

    fn backend(
        &self,
        action: &str,
        program: &Program,
        package: &Package,
        build: Option<(&str, &Path)>,
    ) -> Result<Value> {
        let version_hash = program.tables["versions"]
            .values()
            .find(|row| row["version"].as_str() == program.selection.version.as_deref())
            .and_then(|row| row["version_hash"].as_str());
        let request = json!({
            "action": action,
            "package": {"manifest": package.manifest, "tables": package.tables},
            "entry_impl_hash": program.selection.entry_point,
            "version_hash": version_hash,
            "target": build.map(|(target, _)| target),
            "output": build.map(|(_, path)| path),
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
                _ if action == "build" => "BuildFailed",
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
        let package = self.validate(program)?;
        let report = self.backend("verify", program, &package, None)?;
        if report["ok"] != true {
            return Err(ServerError::new(
                "VerificationFailed",
                report["message"]
                    .as_str()
                    .unwrap_or("required verification failed"),
            ));
        }
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
        revised.reports.insert(args.expected_revision, json!({"workspace_id": args.workspace_id, "revision": args.expected_revision, "report": report}));
        next.snapshots.insert(id.clone(), program.clone());
        let pending = PendingCommit {
            state: next,
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
        self.state = pending.state;
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
        let combined = self.validate(&program)?;
        let report = self.backend("verify", &program, &combined, None)?;
        if report["ok"] != true {
            return Err(ServerError::new(
                "VerificationFailed",
                report["message"]
                    .as_str()
                    .unwrap_or("imported package verification failed"),
            ));
        }
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
        Ok(json!({"snapshot_id": id, "versions": versions}))
    }

    fn build(&self, args: Build) -> Result<Value> {
        let program = self
            .state
            .snapshots
            .get(&args.snapshot_id)
            .filter(|program| program.selection.version.is_some())
            .ok_or_else(|| missing("unknown committed snapshot"))?;
        if args.target != "linux-x86_64" {
            return Err(ServerError::new(
                "UnsupportedProfile",
                "expected linux-x86_64",
            ));
        }
        let package = self.combined_package(program)?;
        let area = tempfile::tempdir_in(self.root.join("artifacts"))?;
        let staged = area.path().join("program");
        let build = self.backend("build", program, &package, Some((&args.target, &staged)))?;
        if !staged.is_file() {
            return Err(ServerError::new(
                "ToolError",
                "backend did not create the artifact",
            ));
        }
        let name = if program.selection.entry_point.is_some() {
            format!("{}-{}", args.snapshot_id, args.target)
        } else {
            format!("libllmlang_{}.rlib", args.snapshot_id)
        };
        let artifact = self.root.join("artifacts").join(name);
        fs::rename(staged, &artifact)?;
        Ok(
            json!({"snapshot_id": args.snapshot_id, "target": args.target,
            "artifact": artifact, "exports": build["exports"]}),
        )
    }

    fn store(&mut self, state: State) -> Result<()> {
        write_atomic(&self.root.join("state.json"), &state)?;
        self.state = state;
        Ok(())
    }

    fn recover(&mut self) -> Result<()> {
        if let Some(pending) = read_optional::<PendingCommit>(&self.root.join("pending.json"))? {
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
                self.store(pending.state)?;
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
        package.manifest.dependencies.clear();
        let area = tempfile::tempdir_in(&self.root)?;
        let path = area.path().join("graph");
        llmlang_spg::save(&path, &package, SaveOptions::default()).map_err(validation)?;
        let graph: Graph = llmlang_spg::load_graph(&path, VERSIONS, GraphLoadOptions::default())
            .map_err(validation)?;
        let node = graph
            .objects()
            .find(|node| node.object().table == table && node.object().storage_key == key)
            .ok_or_else(|| missing("unknown object"))?;
        let link = |(relation, node): (_, llmlang_spg::Node<'_>)| {
            let object = node.object();
            json!({
                "relation": format!("{relation:?}"),
                "uri": format!("llmlang://{scope}/{id}/object/{}/{}", object.table, encode_segment(&object.storage_key)),
            })
        };
        Ok(json!({
            "table": table, "key": key, "content_hash": node.object().content_hash,
            "row": package.tables[table][key],
            "outgoing": node.outgoing().map(link).collect::<Vec<_>>(),
            "incoming": node.incoming().map(link).collect::<Vec<_>>(),
        }))
    }
}

fn view(id: &str, workspace: &Workspace) -> Value {
    let program = &workspace.program;
    let exports: Vec<_> = program.tables["bindings"].values().filter_map(|binding| {
        let interface_hash = binding["interface_hash"].as_str()?;
        let interface = program.tables["interfaces"].get(interface_hash)?;
        Some(json!({"name":interface["name"],"interface_hash":interface_hash,"impl_hash":binding["impl_hash"]}))
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
    fn recovers_published_package_after_interruption() {
        let directory = tempfile::tempdir().unwrap();
        let backend = Path::new(env!("CARGO_MANIFEST_DIR")).join("scalar.py");
        let server = Server::open(directory.path(), "python3", &backend).unwrap();

        let package = Package::empty(Manifest {
            language_version: VERSIONS[0].into(),
            dependencies: BTreeMap::new(),
        });
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
