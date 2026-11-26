use linux_syscalls_provider::{decode_read, decode_write, ReadOutcome, SyscallError};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let [operation, raw, requested] = &args[..] else {
        eprintln!("usage: decoder read|write RAW COUNT");
        std::process::exit(2);
    };
    let raw = raw
        .parse::<isize>()
        .expect("raw Linux result must be isize");
    let requested = requested
        .parse::<usize>()
        .expect("request count must be usize");
    let result = match operation.as_str() {
        "read" => decode_read(raw, requested),
        "write" => decode_write(raw, requested).map(ReadOutcome::Progress),
        _ => panic!("unsupported decoder operation"),
    };
    match result {
        Ok(ReadOutcome::Progress(count)) => println!("progress {count}"),
        Ok(ReadOutcome::Eof) => println!("eof"),
        Err(SyscallError::Kernel(errno)) => println!("errno {}", errno.code()),
        Err(SyscallError::UnexpectedReturn(raw)) => println!("abi_violation {raw}"),
        Err(error) => panic!("unexpected decoder error: {error}"),
    }
}
