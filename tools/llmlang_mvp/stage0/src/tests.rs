use serde_json::json;

use crate::{backend, frontend, model};

const CALCULATOR: &str = include_str!("../../calculator.llmlang");

#[test]
fn deterministic_graph_and_pinned_call() {
    let source = "
def main(x: int, flag: bool) -> int:
    if flag == False:
        return callee(x)
    else:
        return -9223372036854775808

def callee(x: int) -> int:
    value = x + 0x3
    return value
";
    let graph = frontend::lower(source, "test.llmlang", None).unwrap();
    let caller = &graph.functions["main"];
    let callee = &graph.functions["callee"];
    assert_eq!(
        caller.body[0][2][0][1],
        json!(["call", "callee", [["var", "x"]], callee.impl_hash])
    );
    assert_eq!(caller.body[0][3][0][1], json!(["i64", i64::MIN]));

    let other = frontend::lower(&source.replace("0x3", "4"), "test.llmlang", None).unwrap();
    assert_ne!(other.functions["callee"].impl_hash, callee.impl_hash);
    assert_ne!(other.functions["main"].impl_hash, caller.impl_hash);
    let equivalent = frontend::lower(&source.replace("0x3", "3"), "test.llmlang", None).unwrap();
    assert_eq!(
        serde_json::to_value(graph).unwrap(),
        serde_json::to_value(equivalent).unwrap()
    );
}

#[test]
fn source_diagnostics_reject_unknown_scopes_types_and_cycles() {
    let examples = [
        (
            "def entry(x: int) -> int:\n    if True:\n        y = x\n    return y\n",
            "unknown variable",
        ),
        (
            "def entry(x: int) -> int:\n    return entry(x)\n",
            "recursive call",
        ),
        (
            "def entry(x: int) -> int:\n    return 9223372036854775808\n",
            "out of signed 64-bit range",
        ),
        (
            "def entry(x: int) -> int:\n    return x > 0\n",
            "expected return type",
        ),
        (
            "def entry(x: int) -> int:\n    if x:\n        return x\n",
            "if condition must have type bool",
        ),
        (
            "def entry(x: int) -> int:\n    if True:\n        return x\n",
            "must return or fail",
        ),
        (
            "def entry(x: int) -> int:\n    return x\n    x = 1\n",
            "unreachable statement",
        ),
        (
            "def entry(x: int) -> int:\n    return fail('OtherError')\n",
            "supported literal error name",
        ),
    ];
    for (source, expected) in examples {
        let error = frontend::lower(source, "test.llmlang", None).unwrap_err();
        assert!(error.starts_with("line "), "{error}");
        assert!(error.contains(expected), "{error}");
    }
}

#[test]
fn normalizes_compatible_python_identifiers_to_ascii() {
    let unicode = "def K(ｘ: ｉｎｔ) -> int:\r\n    return x\r\n";
    let ascii = "def K(x: int) -> int:\n    return x\n";
    let lower = |source| {
        serde_json::to_value(frontend::lower(source, "test.llmlang", None).unwrap()).unwrap()
    };
    assert_eq!(lower(unicode), lower(ascii));
}

#[test]
fn rejects_stale_spg_bindings_and_changed_bodies() {
    let source = CALCULATOR.replace("return left + right", "return helper(left, right)")
        + "\ndef helper(left: int, right: int) -> int:\n    return left + right\n";
    let mut graph = frontend::lower(&source, "test.llmlang", None).unwrap();
    assert!(backend::emit("calculator", Some(&graph)).is_ok());
    let helper = graph.functions.get_mut("helper").unwrap();
    helper.body[0][1][1] = json!("-");
    assert!(backend::emit("calculator", Some(&graph))
        .unwrap_err()
        .contains("digest mismatch"));
    let helper = graph.functions.get_mut("helper").unwrap();
    helper.impl_hash = helper.identity();
    assert!(backend::emit("calculator", Some(&graph))
        .unwrap_err()
        .contains("unresolved implementation binding"));
}

#[test]
fn rejects_ill_typed_spg_even_when_rehashed() {
    let mut graph = frontend::lower(CALCULATOR, "test.llmlang", None).unwrap();
    let function = graph.functions.get_mut("add").unwrap();
    function.body = vec![json!(["return", ["bool", false]])];
    function.impl_hash = function.identity();
    assert!(backend::emit("calculator", Some(&graph))
        .unwrap_err()
        .contains("expected return type i64, got bool"));
}

#[test]
fn rejects_ambiguous_hash_map_and_incomplete_graph() {
    let ambiguous = serde_json::from_str::<model::ProvidedHashes>(r#"{"add":"one","add":"two"}"#);
    assert!(
        matches!(ambiguous, Err(error) if error.to_string().contains("duplicate function name"))
    );

    let source = "def entry() -> int:\n    return 1\n";
    let mut graph =
        serde_json::to_value(frontend::lower(source, "test.llmlang", None).unwrap()).unwrap();
    graph["functions"]["entry"]
        .as_object_mut()
        .unwrap()
        .remove("provided_contract_hash");
    let parsed = serde_json::from_value::<model::Graph>(graph);
    assert!(matches!(parsed, Err(error) if error.to_string().contains("missing field")));
}
