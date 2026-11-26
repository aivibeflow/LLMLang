use std::ffi::CString;

type LaunchArgs = Vec<Vec<u8>>;

fn errno_message(errno: isize) -> Vec<u8> {
    format!("Error: Kernel(Errno({errno}))\n").into_bytes()
}
