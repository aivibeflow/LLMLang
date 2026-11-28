//! One-time conversion of an offline copy of the v6 server state.

use super::*;

pub(super) fn migrate(server: &mut Server) -> Result<Value> {
    let old = &server.state;
    for (id, workspace) in &old.workspaces {
        if workspace.committed.is_none()
            && (workspace.revision != 0 || !workspace.requests.is_empty())
        {
            return Err(conflict(format!("workspace {id} has uncommitted changes")));
        }
    }
    check_state_layout(old)?;

    let mut dependencies = BTreeMap::new();
    for (id, program) in &old.snapshots {
        if snapshot_id(program)? != *id {
            return Err(validation(format!(
                "v6 snapshot {id} failed its identity check"
            )));
        }
        let pins = program
            .manifest
            .dependencies
            .iter()
            .map(|(name, pin)| server.dependency(name, pin).map(|(id, _)| id.clone()))
            .collect::<Result<Vec<_>>>()?;
        dependencies.insert(id.clone(), pins);
    }
    let old = std::mem::take(&mut server.state);

    let mut converted = BTreeMap::new();
    let mut remaining = old.snapshots.keys().collect::<BTreeSet<_>>();
    let mut smoke_snapshot = None;
    let mut smoke_executable = false;
    while !remaining.is_empty() {
        let old_id = remaining
            .iter()
            .copied()
            .find(|id| {
                dependencies[*id]
                    .iter()
                    .all(|dep| converted.contains_key(dep))
            })
            .ok_or_else(|| validation("dependency cycle in the v6 catalog"))?;
        remaining.remove(old_id);
        let mut program = old.snapshots[old_id].clone();
        for pin in program.manifest.dependencies.values_mut() {
            if let Some(new_id) = converted.get(pin) {
                *pin = String::clone(new_id);
            }
        }
        convert_bindings(&mut program)?;
        refresh_obligations(server, &mut program)?;
        let id = snapshot_id(&program)?;
        server.check_version(&program, &id)?;

        if !smoke_executable && !program.tables["bindings"].is_empty() {
            let mut package = server.combined_package(&program)?;
            match server.native_output(&program, &mut package, native::LINUX_X86_64) {
                Ok(output) if output.executable || smoke_snapshot.is_none() => {
                    smoke_snapshot = Some(id.clone());
                    smoke_executable = output.executable;
                }
                Ok(_) => {}
                Err(error) if error.code == "MissingImplementation" => {}
                Err(error) => return Err(error),
            }
        }
        server.state.snapshots.insert(id.clone(), program);
        converted.insert(old_id.clone(), id);
    }

    server.state.sequence = old.sequence;
    for (id, mut workspace) in old.workspaces {
        workspace.base_snapshot = mapped_id(&converted, &workspace.base_snapshot)?.to_owned();
        if let Some(committed) = workspace.committed.as_mut() {
            *committed = mapped_id(&converted, committed)?.to_owned();
        }
        workspace.program = server.state.snapshots[workspace
            .committed
            .as_ref()
            .unwrap_or(&workspace.base_snapshot)]
        .clone();
        // Requests and verification reports certify the old revision context.
        workspace.requests.clear();
        workspace.reports.clear();
        server.state.workspaces.insert(id, workspace);
    }

    regenerate_packages(server, &old.snapshots, &converted)?;
    write_atomic(&server.root.join("state.json"), &server.state)?;
    Ok(json!({"snapshot_ids": converted, "smoke_snapshot_id": smoke_snapshot}))
}

fn mapped_id<'a>(converted: &'a BTreeMap<String, String>, old: &str) -> Result<&'a str> {
    converted
        .get(old)
        .map(String::as_str)
        .ok_or_else(|| validation(format!("missing migrated snapshot {old}")))
}

fn convert_bindings(program: &mut Program) -> Result<()> {
    let bindings = program.tables.get_mut("bindings").unwrap();
    for (key, mut row) in std::mem::take(bindings) {
        let revision = row["version_hash"]
            .as_str()
            .ok_or_else(|| validation("invalid v6 version hash"))?
            .to_owned();
        let interface = row["interface_hash"]
            .as_str()
            .ok_or_else(|| validation("invalid v6 interface hash"))?
            .to_owned();
        let fields = row
            .as_object_mut()
            .ok_or_else(|| validation("invalid v6 binding"))?;
        let platform = fields
            .remove("platform")
            .filter(Value::is_string)
            .ok_or_else(|| validation("missing v6 binding platform"))?;
        let platform = platform.as_str().unwrap();
        if key != format!("{revision}:{interface}:{platform}")
            || fields.contains_key("arch")
            || fields.contains_key("os")
        {
            return Err(validation("invalid v6 binding key or target columns"));
        }
        let (arch, os) = if platform.is_empty() {
            ("", "")
        } else {
            llmlang_spg::BUILD_TARGETS
                .iter()
                .copied()
                .find(|(arch, os)| platform == format!("{}_{arch}", os.replace('-', "_")))
                .ok_or_else(|| validation(format!("no v7 mapping for v6 platform {platform:?}")))?
        };
        fields.insert("arch".into(), json!(arch));
        fields.insert("os".into(), json!(os));
        if bindings
            .insert(format!("{revision}:{interface}:{arch}:{os}"), row)
            .is_some()
        {
            return Err(conflict("v6 bindings map to the same v7 row"));
        }
    }
    let local = program.package();
    for (version, row) in program.tables.get_mut("versions").unwrap() {
        row["binding_hash"] = json!(changes::binding_identity(&local, version)?);
    }
    Ok(())
}

fn refresh_obligations(server: &Server, program: &mut Program) -> Result<()> {
    let combined = server.combined_package(program)?;
    let catalogs = server.native_catalogs(program)?;
    let callers: BTreeSet<_> = program.tables["verification_obligations"]
        .values()
        .filter(|row| row["kind"] == "call_compatibility")
        .map(|row| {
            row["caller_impl_hash"]
                .as_str()
                .ok_or_else(|| validation("invalid v6 caller"))
        })
        .collect::<Result<_>>()?;
    let mut calls = obligations::CallsByCaller::new();
    for caller in callers {
        let row = program.tables["functions"]
            .get(caller)
            .ok_or_else(|| validation("v6 caller is absent from the package"))?;
        calls.insert(
            caller.to_owned(),
            native::resolved_calls(
                &program.name,
                &combined,
                row,
                &catalogs,
                native::LINUX_X86_64,
            )?,
        );
    }
    let mut package = program.package();
    obligations::replace(&mut package, obligations::rows(&combined, &calls)?);
    program.tables = package.tables;
    let combined = server.combined_package(program)?;
    server.validate_native(program, &combined)?;
    server.validate_native_sources(program, &combined)
}

fn regenerate_packages(
    server: &Server,
    old: &BTreeMap<String, Program>,
    converted: &BTreeMap<String, String>,
) -> Result<()> {
    let root = server.root.join("packages");
    let scratch = tempfile::tempdir_in(&server.root)?;
    let fresh = scratch.path().join("packages");
    fs::create_dir(&fresh)?;
    for name in fs::read_dir(&root)? {
        let name = name?;
        for version in fs::read_dir(name.path())? {
            let version = version?;
            let metadata: PackageMetadata = read_json(&version.path().join("package.json"))?;
            let previous = old.get(&metadata.snapshot_id).ok_or_else(|| {
                validation("saved v6 package is missing from the snapshot catalog")
            })?;
            if server.package_path(previous)? != version.path()
                || metadata.name != previous.name
                || metadata.selection.version != previous.selection.version
                || metadata.selection.entry_point != previous.selection.entry_point
            {
                return Err(validation(
                    "saved v6 package metadata disagrees with its snapshot",
                ));
            }
            let id = mapped_id(converted, &metadata.snapshot_id)?;
            let program = &server.state.snapshots[id];
            let destination = fresh.join(name.file_name()).join(version.file_name());
            fs::create_dir_all(destination.parent().unwrap())?;
            llmlang_spg::save(
                &destination,
                &program.package(),
                SaveOptions {
                    write_text_dump: true,
                },
            )
            .map_err(validation)?;
            write_atomic(
                &destination.join("package.json"),
                &PackageMetadata {
                    name: program.name.clone(),
                    selection: program.selection.clone(),
                    snapshot_id: id.to_owned(),
                },
            )?;
            for entry in fs::read_dir(version.path())? {
                let entry = entry?;
                let target = destination.join(entry.file_name());
                if !target.try_exists()? {
                    fs::rename(entry.path(), target)?;
                }
            }
        }
    }
    fs::rename(&root, scratch.path().join("old-packages"))?;
    fs::rename(fresh, root)?;
    Ok(())
}
