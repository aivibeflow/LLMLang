use std::{
    env,
    ffi::OsString,
    fs,
    io::{self, Write},
    path::Path,
    process::ExitCode,
};

mod backend;
mod frontend;
mod model;

const USAGE: &str = "Usage:
  llmlang-stage0 lower SOURCE [PROVIDED_HASHES_JSON]
  llmlang-stage0 emit-rust calculator|hello|echo

'lower' writes SPG JSON to stdout. 'emit-rust calculator' reads an admitted SPG
from stdin and writes Rust source to stdout. The smoke workload adapters take
no SPG input.";

fn lower(source: &OsString, hashes: Option<&OsString>) -> Result<String, String> {
    let source_path = Path::new(source);
    let text = fs::read_to_string(source_path)
        .map_err(|error| format!("{}: {error}", source_path.display()))?;
    let hashes = hashes
        .map(|path| {
            let raw = fs::read(path)
                .map_err(|error| format!("{}: {error}", Path::new(path).display()))?;
            serde_json::from_slice::<model::ProvidedHashes>(&raw)
                .map(|hashes| hashes.0)
                .map_err(|error| format!("invalid provided hash map: {error}"))
        })
        .transpose()?;
    let graph = frontend::lower(&text, &source_path.to_string_lossy(), hashes)
        .map_err(|error| format!("{}: {error}", source_path.display()))?;
    // Convert the typed graph to ordered JSON maps before encoding.
    let canonical = serde_json::to_value(graph).map_err(|error| error.to_string())?;
    Ok(format!("{canonical}\n"))
}

fn run(args: &[OsString]) -> Result<String, String> {
    match args {
        [action, source, rest @ ..] if action == "lower" && rest.len() <= 1 => {
            lower(source, rest.first())
        }
        [action, workload] if action == "emit-rust" => {
            let workload = workload.to_str().ok_or("invalid workload name")?;
            let graph = if workload == "calculator" {
                Some(
                    serde_json::from_reader(io::stdin().lock())
                        .map_err(|error| format!("invalid SPG JSON: {error}"))?,
                )
            } else {
                None
            };
            backend::emit(workload, graph.as_ref())
        }
        [flag] if flag == "--version" => {
            Ok(format!("llmlang-stage0 {}\n", env!("CARGO_PKG_VERSION")))
        }
        [flag] if flag == "--help" || flag == "-h" => Ok(format!("{USAGE}\n")),
        _ => Err(USAGE.into()),
    }
}

fn main() -> ExitCode {
    let args: Vec<_> = env::args_os().skip(1).collect();
    match run(&args).and_then(|output| {
        io::stdout()
            .lock()
            .write_all(output.as_bytes())
            .map_err(|error| error.to_string())
    }) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("llmlang-stage0: {error}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests;
