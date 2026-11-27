use llmlang_server::{Server, ServerError};
use serde_json::{json, Map, Value};
use std::env;
use std::io::{self, BufRead, Write};
use std::path::PathBuf;
use std::process::ExitCode;

const PROTOCOL_VERSION: &str = "2025-11-25";
const SUPPORTED_VERSIONS: &[&str] = &[PROTOCOL_VERSION, "2025-06-18"];
const USAGE: &str = "Usage: llmlang-server --state-dir PATH [--python PROGRAM] [--backend PATH]";

struct Options {
    state_dir: PathBuf,
    python: String,
    backend: PathBuf,
}

impl Options {
    fn parse() -> Result<Option<Self>, String> {
        let mut state_dir = None;
        let mut python = None;
        let mut backend = None;
        let mut args = env::args_os().skip(1);
        while let Some(flag) = args.next() {
            match flag.to_str() {
                Some("--help" | "-h") => return Ok(None),
                Some("--state-dir") if state_dir.is_none() => {
                    state_dir = Some(PathBuf::from(args.next().ok_or("missing state directory")?));
                }
                Some("--python") if python.is_none() => {
                    python = Some(
                        args.next()
                            .ok_or("missing Python program")?
                            .into_string()
                            .map_err(|_| "Python program must be UTF-8")?,
                    );
                }
                Some("--backend") if backend.is_none() => {
                    backend = Some(PathBuf::from(args.next().ok_or("missing backend path")?));
                }
                _ => return Err(format!("unexpected argument {}", flag.to_string_lossy())),
            }
        }
        Ok(Some(Self {
            state_dir: state_dir.ok_or("--state-dir is required")?,
            python: python.unwrap_or_else(|| "python3".into()),
            backend: backend
                .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("scalar.py")),
        }))
    }
}

struct RpcError {
    code: i32,
    message: &'static str,
    domain: Option<ServerError>,
}

impl RpcError {
    const fn new(code: i32, message: &'static str) -> Self {
        Self {
            code,
            message,
            domain: None,
        }
    }

    fn resource(error: ServerError) -> Self {
        let (code, message) = match error.code {
            "InvalidArguments" => (-32602, "Invalid resource URI"),
            "MissingReference" => (-32002, "Resource unavailable"),
            _ => (-32603, "Resource read failed"),
        };
        Self {
            code,
            message,
            domain: Some(error),
        }
    }

    fn response(self) -> Value {
        let mut error = json!({"code": self.code, "message": self.message});
        if let Some(domain) = self.domain {
            error["data"] = domain_error(&domain);
        }
        error
    }
}

const INVALID_REQUEST: RpcError = RpcError::new(-32600, "Invalid Request");
const INVALID_PARAMS: RpcError = RpcError::new(-32602, "Invalid params");
const METHOD_NOT_FOUND: RpcError = RpcError::new(-32601, "Method not found");

#[derive(Default, PartialEq, Eq)]
enum Session {
    #[default]
    New,
    Initializing,
    Ready,
}

struct Adapter {
    server: Server,
    session: Session,
    tools: Vec<Value>,
}

impl Adapter {
    fn request(&mut self, line: &str) -> Option<Value> {
        let request: Value = match serde_json::from_str(line) {
            Ok(request) => request,
            Err(_) => {
                return Some(response(
                    Value::Null,
                    Err(RpcError::new(-32700, "Parse error")),
                ))
            }
        };
        let Some(request) = request.as_object() else {
            return Some(response(Value::Null, Err(INVALID_REQUEST)));
        };
        let id = request.get("id");
        let Some(method) = request.get("method").and_then(Value::as_str) else {
            return Some(response(Value::Null, Err(INVALID_REQUEST)));
        };
        if request.get("jsonrpc").and_then(Value::as_str) != Some("2.0")
            || id.is_some_and(|id| !(id.is_string() || id.is_i64() || id.is_u64()))
        {
            return Some(response(Value::Null, Err(INVALID_REQUEST)));
        }
        match id {
            None => {
                if method == "notifications/initialized" && self.session == Session::Initializing {
                    self.session = Session::Ready;
                }
                None
            }
            Some(id) => {
                let params = match request.get("params") {
                    None => Some(Map::new()),
                    Some(params) => params.as_object().cloned(),
                };
                let result = params
                    .ok_or(INVALID_PARAMS)
                    .and_then(|params| self.dispatch(method, &params));
                Some(response(id.clone(), result))
            }
        }
    }

    fn dispatch(&mut self, method: &str, params: &Map<String, Value>) -> Result<Value, RpcError> {
        match method {
            "initialize" => {
                if self.session != Session::New {
                    return Err(RpcError::new(-32600, "Already initialized"));
                }
                let requested = required_string(params, "protocolVersion")?;
                let version = if SUPPORTED_VERSIONS.contains(&requested) {
                    requested
                } else {
                    PROTOCOL_VERSION
                };
                self.session = Session::Initializing;
                return Ok(json!({
                    "protocolVersion": version,
                    "serverInfo": {"name": "llmlang-server", "version": env!("CARGO_PKG_VERSION")},
                    "capabilities": {"tools": {}, "resources": {}}
                }));
            }
            "ping" => return Ok(json!({})),
            _ if self.session != Session::Ready => {
                return Err(RpcError::new(-32600, "Initialization required"));
            }
            _ => {}
        }
        match method {
            "tools/list" => Ok(json!({"tools": self.tools})),
            "tools/call" => {
                let name = required_string(params, "name")?;
                if !self
                    .tools
                    .iter()
                    .any(|tool| tool["name"].as_str() == Some(name))
                {
                    return Err(RpcError::new(-32602, "Unknown tool"));
                }
                let arguments = match params.get("arguments") {
                    None => json!({}),
                    Some(value) if value.is_object() => value.clone(),
                    Some(_) => return Err(INVALID_PARAMS),
                };
                Ok(tool_result(self.server.call(name, arguments)))
            }
            "resources/list" => Ok(json!({"resources": []})),
            "resources/templates/list" => Ok(json!({"resourceTemplates": resource_templates()})),
            "resources/read" => {
                let uri = required_string(params, "uri")?;
                let value = self.server.read_resource(uri).map_err(RpcError::resource)?;
                Ok(json!({"contents": [{
                    "uri": uri, "mimeType": "application/json", "text": value.to_string()
                }]}))
            }
            _ => Err(METHOD_NOT_FOUND),
        }
    }
}

fn required_string<'a>(params: &'a Map<String, Value>, key: &str) -> Result<&'a str, RpcError> {
    params
        .get(key)
        .and_then(Value::as_str)
        .filter(|text| !text.is_empty())
        .ok_or(INVALID_PARAMS)
}

fn domain_error(error: &ServerError) -> Value {
    json!({"code": error.code, "message": error.message})
}

fn tool_result(result: Result<Value, ServerError>) -> Value {
    match result {
        Ok(value) => json!({
            "content": [{"type": "text", "text": value.to_string()}],
            "structuredContent": value,
            "isError": false,
        }),
        Err(error) => json!({
            "content": [{"type": "text", "text": domain_error(&error).to_string()}],
            "isError": true,
        }),
    }
}

fn response(id: Value, result: Result<Value, RpcError>) -> Value {
    match result {
        Ok(value) => json!({"jsonrpc": "2.0", "id": id, "result": value}),
        Err(error) => json!({"jsonrpc": "2.0", "id": id, "error": error.response()}),
    }
}

fn record(properties: &[(&str, Value)], optional: &[&str], additional: bool) -> Value {
    let required: Vec<_> = properties
        .iter()
        .filter_map(|(key, _)| (!optional.contains(key)).then_some(*key))
        .collect();
    let properties: Map<String, Value> = properties
        .iter()
        .map(|(key, schema)| (key.to_string(), schema.clone()))
        .collect();
    json!({"type": "object", "properties": properties, "required": required, "additionalProperties": additional})
}

fn tool(name: &str, description: &str, input: Value, output: Value) -> Value {
    json!({"name": name, "description": description, "inputSchema": input, "outputSchema": output})
}

fn string() -> Value {
    json!({"type": "string", "minLength": 1})
}

fn revision() -> Value {
    json!({"type": "integer", "minimum": 0})
}

fn nullable(schema: Value) -> Value {
    json!({"anyOf": [schema, {"type": "null"}]})
}

fn object_ref() -> Value {
    json!({"oneOf": [
        string(),
        record(&[("local", string())], &[], false),
    ]})
}

fn operation(name: &str, fields: &[(&str, Value)], optional: &[&str]) -> Value {
    let mut properties = vec![("op", json!({"const": name}))];
    properties.extend_from_slice(fields);
    record(&properties, optional, false)
}

fn tuple(parts: &[Value]) -> Value {
    json!({
        "type": "array", "minItems": parts.len(), "maxItems": parts.len(),
        "prefixItems": parts,
    })
}

fn body_schema() -> Value {
    let expression = || json!({"$ref": "#/$defs/expression"});
    let statement = || json!({"$ref": "#/$defs/statement"});
    let tag = |name: &str| json!({"const": name});
    json!({
        "expression": {"oneOf": [
            tuple(&[tag("i64"), json!({
                "type": "integer", "minimum": i64::MIN, "maximum": i64::MAX
            })]),
            tuple(&[tag("bool"), json!({"type": "boolean"})]),
            tuple(&[tag("var"), string()]),
            tuple(&[
                tag("bin"),
                json!({"enum": ["+", "-", "*", "/", "==", "!=", "<", "<=", ">", ">="]}),
                expression(),
                expression(),
            ]),
            record(&[
                ("callee_impl_hash", object_ref()),
                ("required_contract_hash", object_ref()),
                ("arguments", json!({"type": "array", "items": expression()})),
            ], &[], false),
        ]},
        "statement": {"oneOf": [
            tuple(&[tag("let"), string(), expression()]),
            tuple(&[tag("return"), expression()]),
            tuple(&[tag("fail"), json!({"enum": ["ArithmeticOverflow", "DivisionByZero", "InvalidInput"]})]),
            tuple(&[
                tag("if"),
                expression(),
                json!({"type": "array", "minItems": 1, "items": statement()}),
                json!({"type": "array", "items": statement()}),
            ]),
        ]},
    })
}

fn operation_schema() -> Value {
    let signature = || {
        record(
            &[
                (
                    "params",
                    json!({"type": "array", "items": {
                        "type": "array", "minItems": 2, "maxItems": 2,
                        "prefixItems": [string(), {"enum": ["i64", "bool"]}]
                    }}),
                ),
                ("result", json!({"enum": ["i64", "bool"]})),
            ],
            &[],
            false,
        )
    };
    let kind = json!({"enum": ["requires", "ensures", "error_declaration", "error_guard"]});
    let rule = record(
        &[
            ("kind", kind),
            ("error_label", string()),
            ("predicate", json!({"type": ["string", "boolean"]})),
        ],
        &["error_label", "predicate"],
        false,
    );
    let put = |name: &str, columns: &[(&str, Value)], optional: &[&str]| {
        let mut fields = vec![
            ("id", string()),
            ("previous", nullable(string())),
            ("expected_hash", nullable(string())),
        ];
        fields.extend_from_slice(columns);
        let mut optional_fields = vec!["previous", "expected_hash"];
        optional_fields.extend_from_slice(optional);
        operation(name, &fields, &optional_fields)
    };
    json!({"oneOf": [
        operation("set_version", &[("version", string()), ("expected_version", nullable(string()))], &[]),
        operation("pin_dependency", &[
            ("name", string()), ("snapshot_id", string()), ("expected_snapshot_id", nullable(string())),
        ], &[]),
        operation("unpin_dependency", &[("name", string()), ("expected_snapshot_id", string())], &[]),
        put("put_contract", &[
            ("typed_signature", signature()), ("rules", json!({"type": "array", "items": rule})),
            ("user_request_texts", json!({"type": "array", "items": {"type": "string"}})),
        ], &["user_request_texts"]),
        put("put_function", &[
            ("typed_signature", signature()), ("canonical_body", json!({"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/statement"}})),
            ("provided_contract", object_ref()),
        ], &[]),
        put("put_interface", &[("name", string()), ("public_contract", object_ref())], &[]),
        operation("bind", &[
            ("interface", object_ref()), ("implementation", object_ref()), ("expected_implementation", nullable(string())),
            ("arch", json!({"type": "string", "pattern": "^[A-Za-z0-9_-]*$", "default": ""})),
            ("os", json!({"type": "string", "pattern": "^[A-Za-z0-9_-]*$", "default": ""})),
        ], &["arch", "os"]),
        operation("unbind", &[("name", string()), ("expected_implementation", string()),
            ("arch", json!({"type": "string", "pattern": "^[A-Za-z0-9_-]*$", "default": ""})),
            ("os", json!({"type": "string", "pattern": "^[A-Za-z0-9_-]*$", "default": ""})),
        ], &["arch", "os"]),
        operation("set_entry_point", &[
            ("implementation", nullable(object_ref())), ("expected_implementation", nullable(string())),
        ], &[]),
        operation("remove_object", &[
            ("table", json!({"enum": ["contracts", "functions", "interfaces"]})),
            ("identity", string()), ("expected_hash", string()),
        ], &[]),
    ]})
}

fn change_set_schema() -> Value {
    let mut schema = record(
        &[
            ("workspace_id", string()),
            ("expected_revision", revision()),
            ("idempotency_key", string()),
            (
                "operations",
                json!({"type": "array", "minItems": 1, "items": operation_schema()}),
            ),
        ],
        &[],
        false,
    );
    schema["$defs"] = body_schema();
    schema
}

fn tools() -> Vec<Value> {
    let workspace = || {
        record(
            &[
                ("workspace_id", string()),
                ("base_snapshot", string()),
                ("revision", revision()),
            ],
            &[],
            true,
        )
    };
    let mutation = || {
        record(
            &[
                ("workspace_id", string()),
                ("expected_revision", revision()),
            ],
            &[],
            false,
        )
    };
    let object = || json!({"type": "object"});
    vec![
        tool(
            "create_package",
            "Open an empty in-memory scalar workspace.",
            record(
                &[
                    ("name", string()),
                    ("language_version", string()),
                    ("profile", string()),
                ],
                &[],
                false,
            ),
            workspace(),
        ),
        tool(
            "import_package",
            "Read and validate a committed package from its directory.",
            record(&[("path", string())], &[], false),
            record(
                &[
                    ("snapshot_id", string()),
                    ("versions", json!({"type": "array"})),
                ],
                &[],
                true,
            ),
        ),
        tool(
            "open_workspace",
            "Open an isolated workspace on an immutable snapshot.",
            record(&[("snapshot_id", string())], &[], false),
            workspace(),
        ),
        tool(
            "inspect_workspace",
            "Inspect a workspace revision, package selection, and graph views.",
            record(&[("workspace_id", string())], &[], false),
            record(
                &[
                    ("workspace_id", string()),
                    ("base_snapshot", string()),
                    ("revision", revision()),
                    ("state", string()),
                    ("manifest", object()),
                    ("exports", json!({})),
                    ("entry_point", json!({})),
                ],
                &[],
                true,
            ),
        ),
        tool(
            "apply_change_set",
            "Validate and apply a batch to an exact workspace revision.",
            change_set_schema(),
            record(
                &[
                    ("workspace_id", string()),
                    ("revision", revision()),
                    ("identities", object()),
                    (
                        "affected_functions",
                        json!({"type": "array", "items": string()}),
                    ),
                ],
                &[],
                true,
            ),
        ),
        tool(
            "verify_workspace",
            "Preview verification on an exact workspace revision.",
            mutation(),
            record(
                &[
                    ("workspace_id", string()),
                    ("revision", revision()),
                    ("report", object()),
                ],
                &[],
                true,
            ),
        ),
        tool(
            "commit_workspace",
            "Verify and publish a persistable workspace. Scalar workspaces are in-memory only.",
            mutation(),
            record(
                &[
                    ("snapshot_id", string()),
                    ("package_path", string()),
                    ("revision", revision()),
                ],
                &[],
                true,
            ),
        ),
        tool(
            "build_package",
            "Build a selected snapshot for a supported target.",
            record(
                &[("snapshot_id", string()), ("target", string())],
                &[],
                false,
            ),
            record(
                &[
                    ("artifact", string()),
                    ("debug_artifact", string()),
                    ("snapshot_id", string()),
                    ("target", string()),
                ],
                &["debug_artifact"],
                true,
            ),
        ),
    ]
}

fn resource_templates() -> Value {
    json!([
        {"name": "workspace", "uriTemplate": "llmlang://workspace/{workspace_id}", "mimeType": "application/json"},
        {"name": "workspace_object", "uriTemplate": "llmlang://workspace/{workspace_id}/object/{table}/{id}", "mimeType": "application/json"},
        {"name": "snapshot_object", "uriTemplate": "llmlang://snapshot/{snapshot_id}/object/{table}/{id}", "mimeType": "application/json"},
        {"name": "verification", "uriTemplate": "llmlang://workspace/{workspace_id}/verification/{revision}", "mimeType": "application/json"}
    ])
}

fn run(options: Options) -> Result<(), String> {
    let server = Server::open(&options.state_dir, &options.python, &options.backend)
        .map_err(|error| format!("{}: {}", error.code, error.message))?;
    let mut adapter = Adapter {
        server,
        session: Session::default(),
        tools: tools(),
    };
    let mut stdout = io::stdout().lock();
    for line in io::stdin().lock().lines() {
        if let Some(reply) = adapter.request(&line.map_err(|error| error.to_string())?) {
            serde_json::to_writer(&mut stdout, &reply).map_err(|error| error.to_string())?;
            stdout
                .write_all(b"\n")
                .and_then(|()| stdout.flush())
                .map_err(|error| error.to_string())?;
        }
    }
    Ok(())
}

fn main() -> ExitCode {
    match Options::parse() {
        Ok(None) => {
            println!("{USAGE}");
            ExitCode::SUCCESS
        }
        Ok(Some(options)) => match run(options) {
            Ok(()) => ExitCode::SUCCESS,
            Err(error) => {
                eprintln!("llmlang-server: {error}");
                ExitCode::FAILURE
            }
        },
        Err(error) => {
            eprintln!("llmlang-server: {error}\n{USAGE}");
            ExitCode::from(2)
        }
    }
}
