use llmlang_spg::*;
use serde_json::json;
use std::{collections::BTreeMap, fs, path::Path};

const VERSIONS: &[&str] = &["0.1.0"];

fn fixture() -> Package {
    let mut package = Package::empty(Manifest {
        language_version: VERSIONS[0].into(),
        dependencies: BTreeMap::from([("stdlib".into(), "pinned-package".into())]),
    });
    let rows = package.tables.get_mut("functions").unwrap();
    rows.insert(
        "second".into(),
        json!({"impl_hash": "second", "typed_signature": {}, "canonical_body": [null, false, [], {}], "provided_contract_hash": "contract"}),
    );
    rows.insert(
        "first".into(),
        json!({"impl_hash": "first", "typed_signature": {}, "canonical_body": {"literal": i64::MIN}, "provided_contract_hash": "contract"}),
    );
    package.tables.get_mut("versions").unwrap().insert(
        "v".into(),
        json!({"version_hash": "v", "version": "v", "binding_hash": "bindings"}),
    );
    package
}

fn read(path: &Path, file: &str) -> Vec<u8> {
    fs::read(path.join(file)).unwrap()
}

#[test]
fn round_trip_binary_and_protojson() {
    let area = tempfile::tempdir().unwrap();
    let binary = area.path().join("binary");
    let with_text = area.path().join("with-text");
    let exported = area.path().join("exported");
    let package = fixture();
    save(&binary, &package, SaveOptions::default()).unwrap();
    save(
        &with_text,
        &package,
        SaveOptions {
            write_text_dump: true,
        },
    )
    .unwrap();
    let options = LoadOptions {
        write_text_dump: true,
        text_dump_dir: Some(&exported),
    };
    assert_eq!(load(&binary, VERSIONS, options).unwrap(), package);
    assert_eq!(
        load(&with_text, VERSIONS, LoadOptions::default()).unwrap(),
        package
    );
    assert_eq!(
        read(&binary, "manifest.json"),
        read(&with_text, "manifest.json")
    );
    for table in TABLES {
        for extension in ["dump", "index.json"] {
            let name = format!("{table}.{extension}");
            assert_eq!(read(&binary, &name), read(&with_text, &name));
        }
        let name = format!("{table}.json");
        assert!(!binary.join(&name).exists());
        assert_eq!(read(&with_text, &name), read(&exported, &name));
    }
    assert_eq!(read(&exported, "interfaces.json"), b"[]\n");
    let rows: serde_json::Value =
        serde_json::from_slice(&read(&exported, "functions.json")).unwrap();
    assert_eq!(rows[0]["key"], "first");
    assert_eq!(
        rows[0]["canonicalBody"]["objectValue"]["fields"][0]["value"]["intValue"],
        "-9223372036854775808",
    );
    assert_eq!(rows[1]["key"], "second");
}

#[test]
fn random_access_cache_and_index_rebuild() {
    let area = tempfile::tempdir().unwrap();
    let path = area.path().join("package");
    let package = fixture();
    save(&path, &package, SaveOptions::default()).unwrap();
    let row = package.tables["functions"]["second"].clone();
    let hash = content_hash("second", &row).unwrap();
    let expected = Some(("second".into(), row.clone()));
    assert_eq!(
        load_record(&path, VERSIONS, "functions", &hash, None).unwrap(),
        expected
    );
    let index = read(&path, "functions.index.json");
    fs::remove_file(path.join("functions.index.json")).unwrap();
    rebuild_index(&path, VERSIONS, "functions").unwrap();
    assert_eq!(read(&path, "functions.index.json"), index);
    fs::remove_file(path.join("functions.dump")).unwrap();
    let cache = BTreeMap::from([(hash.clone(), ("second".into(), row))]);
    assert_eq!(
        load_record(&path, VERSIONS, "functions", &hash, Some(&cache)).unwrap(),
        expected
    );
    assert!(load_record(&path, VERSIONS, "functions", &hash, None).is_err());
}

#[test]
fn rejects_invalid_versions_indexes_and_frames() {
    let area = tempfile::tempdir().unwrap();
    let path = area.path().join("package");
    let output = area.path().join("text");
    let package = fixture();
    save(&path, &package, SaveOptions::default()).unwrap();
    assert!(load(&path, &["9.9.9"], LoadOptions::default()).is_err());
    let manifest = read(&path, "manifest.json");
    let old_manifest = String::from_utf8(manifest.clone())
        .unwrap()
        .replace("llmlang.spg.tables.v2", "llmlang.spg.tables.v1");
    fs::write(path.join("manifest.json"), old_manifest).unwrap();
    let error = load(&path, VERSIONS, LoadOptions::default()).unwrap_err();
    assert!(error.to_string().contains("unsupported repository profile"));
    fs::write(path.join("manifest.json"), b"{}").unwrap();
    assert!(load(&path, VERSIONS, LoadOptions::default()).is_err());
    fs::write(path.join("manifest.json"), manifest).unwrap();
    let hash = content_hash("first", &package.tables["functions"]["first"]).unwrap();
    fs::write(
        path.join("functions.index.json"),
        format!("{{\"{hash}\":999999}}\n"),
    )
    .unwrap();
    assert!(load_record(&path, VERSIONS, "functions", &hash, None).is_err());
    assert!(load(&path, VERSIONS, LoadOptions::default()).is_err());
    rebuild_index(&path, VERSIONS, "functions").unwrap();
    let mut dump = read(&path, "functions.dump");
    dump[16] ^= 1;
    fs::write(path.join("functions.dump"), &dump).unwrap();
    assert!(rebuild_index(&path, VERSIONS, "functions").is_err());
    let options = LoadOptions {
        write_text_dump: true,
        text_dump_dir: Some(&output),
    };
    assert!(load(&path, VERSIONS, options).is_err());
    assert!(!output.exists());
    assert!(save(&path, &package, SaveOptions::default()).is_err());
}

#[test]
fn all_tables_round_trip_with_their_own_columns() {
    let area = tempfile::tempdir().unwrap();
    let path = area.path().join("package");
    let mut package = fixture();
    for (table, row) in [
        (
            "interfaces",
            json!({"interface_hash": "i", "name": "f", "public_contract_hash": "c"}),
        ),
        (
            "contracts",
            json!({"contract_hash": "c", "contract_kind": "function", "profile": "scalar", "typed_signature": {}, "user_request_texts": ["request"], "review_records": [{"decision": "approved"}]}),
        ),
        (
            "contract_rules",
            json!({"contract_hash": "c", "rule_hash": "r", "kind": "requires", "predicate": true}),
        ),
        (
            "bindings",
            json!({"version_hash": "v", "interface_hash": "i", "impl_hash": "first"}),
        ),
        (
            "structures",
            json!({"struct_impl_hash": "s", "type_hash": "t", "canonical_declaration": {}}),
        ),
        (
            "structure_types",
            json!({"type_hash": "t", "identity_hash": "id", "aggregate_kind": "struct", "ordered_member_types": [], "representation_requirements": {}}),
        ),
        (
            "structure_layouts",
            json!({"layout_hash": "l", "type_hash": "t", "target_abi_profile": {}, "layout_descriptor": {}}),
        ),
        (
            "structure_bindings",
            json!({"version_hash": "v", "name": "s", "struct_impl_hash": "s"}),
        ),
        (
            "verification_obligations",
            json!({"obligation_hash": "o", "kind": "body_conformance", "caller_impl_hash": "first", "verification_context_hash": "ctx"}),
        ),
        (
            "verification_runs",
            json!({"run_id": "run", "obligation_hash": "o", "status": "proved", "toolchain_digest": "toolchain", "evidence_ref": "evidence", "checked_at": "2026-11-26T00:00:00Z"}),
        ),
    ] {
        package
            .tables
            .get_mut(table)
            .unwrap()
            .insert("row".into(), row);
    }
    save(&path, &package, SaveOptions::default()).unwrap();
    assert_eq!(
        load(&path, VERSIONS, LoadOptions::default()).unwrap(),
        package
    );

    let wrong = area.path().join("wrong");
    let version = package.tables["versions"]["v"].clone();
    package
        .tables
        .get_mut("functions")
        .unwrap()
        .insert("wrong".into(), version);
    let error = save(&wrong, &package, SaveOptions::default()).unwrap_err();
    assert!(error.to_string().contains("functions: unknown column"));
    assert!(!wrong.exists());
}
