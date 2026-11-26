use llmlang_spg::{
    load_graph, save, GraphLoadOptions, Manifest, Package, Relation, Row, SaveOptions,
};
use serde_json::{json, Value};
use std::{collections::BTreeMap, fs, sync::Arc};

const VERSIONS: &[&str] = &["0.1.0"];

fn package() -> Package {
    Package::empty(Manifest {
        language_version: VERSIONS[0].into(),
        dependencies: Default::default(),
    })
}

fn insert(package: &mut Package, table: &str, key: &str, row: Value) {
    package
        .tables
        .get_mut(table)
        .unwrap()
        .insert(key.into(), row);
}

fn contract(package: &mut Package) {
    insert(
        package,
        "contracts",
        "contract",
        json!({
            "contract_hash": "contract", "contract_kind": "function", "profile": "scalar",
            "typed_signature": {}, "user_request_texts": [], "review_records": []
        }),
    );
}

fn function(package: &mut Package, key: &str, body: Value) {
    let signature = package
        .stage_function_signature("scalar", &json!({"parameters": [], "result": "I64"}))
        .unwrap();
    insert(
        package,
        "functions",
        key,
        json!({
            "impl_hash": key, "function_signature_hash": signature, "canonical_body": body,
            "provided_contract_hash": "contract"
        }),
    );
}

#[test]
fn reload_shares_cached_objects_and_resolves_new_edges() {
    let directory = tempfile::tempdir().unwrap();
    let initial_path = directory.path().join("initial");
    let updated_path = directory.path().join("updated");
    let mut data = package();
    contract(&mut data);
    function(&mut data, "callee", json!({}));
    function(&mut data, "removed", json!({}));
    save(&initial_path, &data, SaveOptions::default()).unwrap();
    let initial = load_graph(&initial_path, VERSIONS, GraphLoadOptions::default()).unwrap();
    assert_eq!(data.tables["function_signatures"].len(), 1);
    let shared = |name| {
        initial
            .get("functions", &[name])
            .unwrap()
            .outgoing()
            .find(|(relation, _)| *relation == Relation::Signature)
            .unwrap()
            .1
    };
    assert!(Arc::ptr_eq(
        shared("callee").object(),
        shared("removed").object()
    ));

    data.tables.get_mut("functions").unwrap().remove("removed");
    function(
        &mut data,
        "caller",
        json!({"args": [{
            "callee_impl_hash": "callee", "required_contract_hash": "contract"
        }]}),
    );
    save(&updated_path, &data, SaveOptions::default()).unwrap();
    // A fully cached table must work without opening its dump at all.
    fs::remove_file(updated_path.join("contracts.dump")).unwrap();
    // The first frame in the mixed table is cached. Corrupt just its LZ4 payload.
    let path = updated_path.join("functions.dump");
    let mut dump = fs::read(&path).unwrap();
    dump[48] ^= 255;
    fs::write(path, dump).unwrap();

    let updated = load_graph(
        &updated_path,
        VERSIONS,
        GraphLoadOptions {
            previous: Some(&initial),
            ..Default::default()
        },
    )
    .unwrap();
    assert!(updated.get("functions", &["removed"]).is_none());
    let caller = updated.get("functions", &["caller"]).unwrap();
    let (callee, required) = caller.calls().next().unwrap();
    assert!(matches!(callee.object().row, Row::Function(_)));
    assert!(Arc::ptr_eq(
        callee.object(),
        initial.get("functions", &["callee"]).unwrap().object()
    ));
    assert!(Arc::ptr_eq(
        required.object(),
        initial.get("contracts", &["contract"]).unwrap().object()
    ));
    assert!(callee
        .incoming()
        .any(|(relation, node)| relation == Relation::Callee
            && Arc::ptr_eq(node.object(), caller.object())));
}

#[test]
fn resolves_declared_dependency_and_rejects_missing_targets() {
    let directory = tempfile::tempdir().unwrap();
    let dependency_path = directory.path().join("dependency");
    let mut dependency = package();
    contract(&mut dependency);
    let signature_hash = dependency
        .stage_function_signature("scalar", &json!({"parameters": [], "result": "I64"}))
        .unwrap();
    save(&dependency_path, &dependency, SaveOptions::default()).unwrap();
    let dependency = load_graph(&dependency_path, VERSIONS, GraphLoadOptions::default()).unwrap();

    let mut data = package();
    data.manifest
        .dependencies
        .insert("stdlib".into(), "exact-pin".into());
    function(&mut data, "caller", json!({}));
    data.tables
        .get_mut("function_signatures")
        .unwrap()
        .remove(&signature_hash);
    let path = directory.path().join("package");
    save(&path, &data, SaveOptions::default()).unwrap();
    assert!(load_graph(&path, VERSIONS, GraphLoadOptions::default()).is_err());
    let resolve = || GraphLoadOptions {
        dependencies: BTreeMap::from([("exact-pin", &dependency)]),
        ..Default::default()
    };
    let graph = load_graph(&path, VERSIONS, resolve()).unwrap();
    let caller = graph.get("functions", &["caller"]).unwrap();
    let signature = caller
        .outgoing()
        .find(|(relation, _)| *relation == Relation::Signature)
        .unwrap()
        .1;
    assert!(Arc::ptr_eq(
        signature.object(),
        dependency
            .get("function_signatures", &[&signature_hash])
            .unwrap()
            .object(),
    ));
    let (relation, target) = caller.outgoing().next().unwrap();
    assert_eq!(relation, Relation::ProvidedContract);
    assert!(Arc::ptr_eq(
        target.object(),
        dependency.get("contracts", &["contract"]).unwrap().object()
    ));

    function(
        &mut data,
        "caller",
        json!({
            "callee_impl_hash": "missing", "required_contract_hash": "contract"
        }),
    );
    let invalid = directory.path().join("invalid");
    save(&invalid, &data, SaveOptions::default()).unwrap();
    assert!(load_graph(&invalid, VERSIONS, resolve())
        .unwrap_err()
        .to_string()
        .contains("missing Callee target"));
}

#[test]
fn canonical_signatures_validate_exact_type_pins_and_hashes() {
    let directory = tempfile::tempdir().unwrap();
    let mut data = package();
    contract(&mut data);
    let typed = json!({
        "parameters": [{"name": "value", "type": {"struct_impl_hash": "structure"}}],
        "result": "I64",
    });
    let hash = data.stage_function_signature("scalar", &typed).unwrap();
    let text = data.tables["function_signatures"][&hash]["function_signature_content"]
        .as_str()
        .unwrap()
        .to_owned();
    assert_eq!(
        llmlang_spg::resolve_function_signature(&hash, &text)
            .unwrap()
            .typed,
        typed
    );
    assert!(llmlang_spg::resolve_function_signature(&hash, &format!("{text} ")).is_err());
    assert!(llmlang_spg::resolve_function_signature("wrong", &text).is_err());

    let changed = json!({
        "parameters": [{"name": "value", "type": {"struct_impl_hash": "another"}}],
        "result": "I64",
    });
    assert_ne!(
        data.stage_function_signature("scalar", &changed).unwrap(),
        hash
    );
    let left = json!({"parameters": [{"name":"left","type":"I64"},{"name":"right","type":"Bool"}], "result":"I64"});
    let mut right = left.clone();
    right["parameters"].as_array_mut().unwrap().reverse();
    assert_ne!(
        data.stage_function_signature("scalar", &left).unwrap(),
        data.stage_function_signature("scalar", &right).unwrap()
    );
    right["result"] = json!("Bool");
    assert_ne!(
        data.stage_function_signature("scalar", &left).unwrap(),
        data.stage_function_signature("scalar", &right).unwrap()
    );

    let row = json!({"impl_hash": "f", "function_signature_hash": hash,
        "provided_contract_hash": "contract", "canonical_body": "{ value }"});
    insert(&mut data, "functions", "f", row.clone());
    let missing_type = directory.path().join("missing-type");
    save(&missing_type, &data, SaveOptions::default()).unwrap();
    assert!(
        load_graph(&missing_type, VERSIONS, GraphLoadOptions::default())
            .unwrap_err()
            .to_string()
            .contains("missing Structure target")
    );

    let mut embedded = row.clone();
    embedded["canonical_body"] = json!("fn f(value: I64) -> I64 { value }");
    insert(&mut data, "functions", "f", embedded);
    let invalid_body = directory.path().join("invalid-body");
    assert!(save(&invalid_body, &data, SaveOptions::default()).is_err());

    insert(&mut data, "functions", "f", row);
    data.tables
        .get_mut("function_signatures")
        .unwrap()
        .remove(&hash);
    let missing_signature = directory.path().join("missing-signature");
    assert!(save(&missing_signature, &data, SaveOptions::default())
        .unwrap_err()
        .to_string()
        .contains("unresolved function signature"));
}
