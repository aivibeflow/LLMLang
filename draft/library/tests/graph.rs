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
    insert(
        package,
        "functions",
        key,
        json!({
            "impl_hash": key, "typed_signature": {}, "canonical_body": body,
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
    save(&dependency_path, &dependency, SaveOptions::default()).unwrap();
    let dependency = load_graph(&dependency_path, VERSIONS, GraphLoadOptions::default()).unwrap();

    let mut data = package();
    data.manifest
        .dependencies
        .insert("stdlib".into(), "exact-pin".into());
    function(&mut data, "caller", json!({}));
    let path = directory.path().join("package");
    save(&path, &data, SaveOptions::default()).unwrap();
    assert!(load_graph(&path, VERSIONS, GraphLoadOptions::default()).is_err());
    let resolve = || GraphLoadOptions {
        dependencies: BTreeMap::from([("exact-pin", &dependency)]),
        ..Default::default()
    };
    let graph = load_graph(&path, VERSIONS, resolve()).unwrap();
    let caller = graph.get("functions", &["caller"]).unwrap();
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
