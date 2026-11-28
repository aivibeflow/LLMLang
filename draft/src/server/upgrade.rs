//! One-time conversion of an offline copy of pre-composite server state.

use super::*;

pub(super) fn migrate(server: &mut Server, format: u8) -> Result<Value> {
    if !matches!(format, 6..=8) {
        return Err(invalid("expected v6, v7, or v8 state format"));
    }
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
                "snapshot {id} failed its identity check"
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
    let mut signature_ids = BTreeMap::new();
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
            .ok_or_else(|| validation("dependency cycle in the old catalog"))?;
        remaining.remove(old_id);
        let mut program = old.snapshots[old_id].clone();
        for pin in program.manifest.dependencies.values_mut() {
            if let Some(new_id) = converted.get(pin) {
                *pin = String::clone(new_id);
            }
        }
        if format == 6 {
            convert_bindings(&mut program)?;
        }
        if format < 8 {
            convert_language(&mut program, &mut signature_ids)?;
        }
        convert_contracts(server, &mut program)?;
        server.validate_edit(&mut program)?;
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

fn convert_language(
    program: &mut Program,
    signature_ids: &mut BTreeMap<String, String>,
) -> Result<()> {
    if program.manifest.language_version != "0.1.0"
        || !program
            .manifest
            .language_component_registry_digest
            .is_empty()
    {
        return Err(validation(
            "no migration mapping for the old language definition",
        ));
    }
    program.manifest.language_version = llmlang_spg::LANGUAGE_VERSION.into();
    program.manifest.language_component_registry_digest =
        llmlang_spg::language_component_registry_digest();

    let mut package = program.package();
    let old_signatures = std::mem::take(package.tables.get_mut("function_signatures").unwrap());
    for (old_hash, row) in old_signatures {
        let text = row["function_signature_content"]
            .as_str()
            .ok_or_else(|| validation("missing old signature text"))?;
        let (profile, new_text) = text
            .split_once(' ')
            .ok_or_else(|| validation("missing old signature profile"))?;
        if profile != "linux-x86_64-native-v1" || row["function_signature_hash"] != old_hash {
            return Err(validation("invalid old signature profile or key"));
        }
        let mut digest = Sha256::new();
        digest.update(b"llmlang-function-signature/v1\0");
        digest.update(profile.as_bytes());
        digest.update(b"\0");
        digest.update(text.as_bytes());
        if old_hash != format!("sha256:{:x}", digest.finalize()) {
            return Err(validation("old function signature hash mismatch"));
        }
        let signature = llmlang_spg::parse_function_signature(&program.manifest, new_text)
            .map_err(validation)?;
        let new_hash = package
            .stage_function_signature(&signature.typed)
            .map_err(validation)?;
        signature_ids.insert(old_hash, new_hash);
    }
    for row in package.tables.get_mut("functions").unwrap().values_mut() {
        let old_hash = row["function_signature_hash"]
            .as_str()
            .ok_or_else(|| validation("missing old function signature hash"))?;
        row["function_signature_hash"] = json!(mapped_id(signature_ids, old_hash)?);
    }
    program.tables = package.tables;
    Ok(())
}

fn convert_contracts(server: &Server, program: &mut Program) -> Result<()> {
    let mut package = program.package();
    let mut contract_ids = BTreeMap::new();
    let mut interface_ids = BTreeMap::new();
    let rules = &package.tables["contract_rules"];
    let owned_rules: BTreeMap<_, BTreeSet<_>> = package.tables["contracts"]
        .keys()
        .map(|hash| {
            (
                hash.clone(),
                rules
                    .values()
                    .filter(|row| row["contract_hash"] == *hash)
                    .filter_map(|row| row["rule_hash"].as_str().map(str::to_owned))
                    .collect(),
            )
        })
        .collect();
    for (old, mut row) in std::mem::take(package.tables.get_mut("contracts").unwrap()) {
        let kind = row["contract_kind"]
            .as_str()
            .ok_or_else(|| validation("missing old contract kind"))?
            .to_owned();
        let fields = row
            .as_object_mut()
            .ok_or_else(|| validation("invalid old contract"))?;
        if fields.remove("profile").is_none() {
            return Err(validation("missing old contract profile"));
        }
        if kind == "function" && fields.remove("typed_signature").is_none() {
            return Err(validation("missing old function contract signature"));
        }
        let hash = changes::contract_identity(
            &package.manifest,
            &kind,
            &row["state_signature"],
            owned_rules[&old].iter(),
        )?;
        row["contract_hash"] = json!(hash);
        let contracts = package.tables.get_mut("contracts").unwrap();
        if let Some(existing) = contracts.get_mut(&hash) {
            for field in ["user_request_texts", "review_records"] {
                let mut entries = existing[field].as_array().cloned().unwrap_or_default();
                for item in row[field].as_array().into_iter().flatten() {
                    if !entries.contains(item) {
                        entries.push(item.clone());
                    }
                }
                existing[field] = json!(entries);
                row[field] = existing[field].clone();
            }
            if existing != &row {
                return Err(validation("conflicting migrated contract rows"));
            }
        } else {
            contracts.insert(hash.clone(), row);
        }
        contract_ids.insert(old.clone(), hash);
    }
    let rules = package.tables.get_mut("contract_rules").unwrap();
    for (_, mut row) in std::mem::take(rules) {
        let owner = mapped_id(
            &contract_ids,
            row["contract_hash"]
                .as_str()
                .ok_or_else(|| validation("missing rule owner"))?,
        )?;
        let rule = row["rule_hash"]
            .as_str()
            .ok_or_else(|| validation("missing rule hash"))?;
        let key = format!("{owner}:{rule}");
        row["contract_hash"] = json!(owner);
        rules.insert(key, row);
    }
    let interfaces = std::mem::take(package.tables.get_mut("interfaces").unwrap());
    for (old, mut row) in interfaces {
        let public = row["public_contract_hash"]
            .as_str()
            .ok_or_else(|| validation("missing public contract"))?;
        let contract = mapped_id(&contract_ids, public)?;
        let name = row["name"]
            .as_str()
            .ok_or_else(|| validation("missing public name"))?;
        let identity = changes::interface_identity(name, contract)?;
        row["interface_hash"] = json!(identity);
        row["public_contract_hash"] = json!(contract);
        package
            .tables
            .get_mut("interfaces")
            .unwrap()
            .insert(identity.clone(), row);
        interface_ids.insert(old, identity);
    }
    for row in package.tables.get_mut("bindings").unwrap().values_mut() {
        row["interface_hash"] = json!(mapped_id(
            &interface_ids,
            row["interface_hash"]
                .as_str()
                .ok_or_else(|| validation("missing binding interface"))?
        )?);
    }
    for row in package.tables.get_mut("structures").unwrap().values_mut() {
        if let Some(old) = row["contract_hash"].as_str() {
            row["contract_hash"] = json!(mapped_id(&contract_ids, old)?);
        }
    }
    for table in ["verification_obligations", "verification_runs"] {
        package.tables.get_mut(table).unwrap().clear();
    }
    changes::rebuild_selection(&mut package, &program.selection)?;
    program.tables = package.tables;
    let combined = server.combined_package(program)?;
    let catalogs = server.native_catalogs(program)?;
    let mut mapped = BTreeMap::new();
    let functions = program.tables.get_mut("functions").unwrap();
    for (old, mut row) in std::mem::take(functions) {
        let contract = mapped_id(
            &contract_ids,
            row["provided_contract_hash"]
                .as_str()
                .ok_or_else(|| validation("missing provided contract"))?,
        )?;
        row["provided_contract_hash"] = json!(contract);
        let hash =
            native::implementation_identity(&program.name, &combined, &row, &catalogs[&old])?;
        row["impl_hash"] = json!(hash);
        functions.insert(hash.clone(), row);
        mapped.insert(old, hash);
    }
    for row in program.tables.get_mut("bindings").unwrap().values_mut() {
        row["impl_hash"] = json!(mapped_id(
            &mapped,
            row["impl_hash"]
                .as_str()
                .ok_or_else(|| validation("missing binding implementation"))?
        )?);
    }
    if let Some(old) = &mut program.selection.entry_point {
        *old = mapped_id(&mapped, old)?.into();
    }
    let mut package = program.package();
    changes::rebuild_selection(&mut package, &program.selection)?;
    program.tables = package.tables;
    Ok(())
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
            let previous = old
                .get(&metadata.snapshot_id)
                .ok_or_else(|| validation("saved package is missing from the snapshot catalog"))?;
            if server.package_path(previous)? != version.path()
                || metadata.name != previous.name
                || metadata.selection.version != previous.selection.version
                || metadata.selection.entry_point != previous.selection.entry_point
            {
                return Err(validation(
                    "saved package metadata disagrees with its snapshot",
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
