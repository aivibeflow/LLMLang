#[path = "src/syscall_lowering.rs"]
mod syscall_lowering;

fn main() {
    let directory = std::path::PathBuf::from(std::env::var_os("OUT_DIR").expect("Cargo OUT_DIR"));
    println!("cargo:rerun-if-changed=src/syscall_lowering.rs");
    for (source, target, lower) in [
        (
            "src/open.llmlang",
            "open.rs",
            syscall_lowering::lower as fn(&str) -> _,
        ),
        (
            "src/native.llmlang",
            "native_syscalls.rs",
            syscall_lowering::lower_native,
        ),
    ] {
        println!("cargo:rerun-if-changed={source}");
        let input =
            std::fs::read_to_string(source).unwrap_or_else(|error| panic!("{source}: {error}"));
        let output = lower(&input).unwrap_or_else(|error| panic!("{source}: {error}"));
        std::fs::write(directory.join(target), output).expect("write lowered LLMLang syscall body");
    }
}
