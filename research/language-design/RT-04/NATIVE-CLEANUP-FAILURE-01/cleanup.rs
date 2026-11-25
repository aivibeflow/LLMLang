use std::io::{self, Write};
use std::panic;

fn event(text: &str) {
    let mut output = io::stdout().lock();
    writeln!(output, "{text}").unwrap();
    output.flush().unwrap();
}

struct Guard {
    label: &'static str,
    fails: bool,
}

impl Drop for Guard {
    fn drop(&mut self) {
        event(self.label);
        if self.fails {
            panic!("close-panic");
        }
    }
}

fn body(mode: &str) -> Result<(), &'static str> {
    match mode {
        "ok" => {
            event("body-ok");
            Ok(())
        }
        "error" => {
            event("body-error");
            Err("body-error")
        }
        "panic" => {
            event("body-panic");
            panic!("body-panic")
        }
        _ => unreachable!(),
    }
}

fn implicit(mode: &str, fails: bool) -> &'static str {
    let _outer = Guard { label: "outer-drop", fails: false };
    let _inner = Guard { label: "inner-drop", fails };
    match body(mode) {
        Ok(()) => "ok",
        Err(reason) => reason,
    }
}

fn close(fails: bool) -> Result<(), &'static str> {
    if fails {
        event("close-error");
        Err("close-error")
    } else {
        event("close-ok");
        Ok(())
    }
}

enum Failure {
    Body(&'static str),
    Cleanup(&'static str),
    Both { body: &'static str, cleanup: &'static str },
}

fn explicit(mode: &str, fails: bool) -> Result<(), Failure> {
    let _outer = Guard { label: "outer-drop", fails: false };
    let original = body(mode);
    let cleanup = close(fails);
    match (original, cleanup) {
        (Ok(()), Ok(())) => Ok(()),
        (Err(reason), Ok(())) => Err(Failure::Body(reason)),
        (Ok(()), Err(reason)) => Err(Failure::Cleanup(reason)),
        (Err(body), Err(cleanup)) => Err(Failure::Both { body, cleanup }),
    }
}

fn main() {
    panic::set_hook(Box::new(|info| {
        match info.payload().downcast_ref::<&str>().copied() {
            Some("body-panic") => event("hook-body"),
            Some("close-panic") => event("hook-close"),
            _ => (),
        }
    }));
    let args: Vec<String> = std::env::args().collect();
    let fails = args[3] == "failure";
    let observed = panic::catch_unwind(|| match args[1].as_str() {
        "implicit" => implicit(&args[2], fails).to_owned(),
        "explicit" => match explicit(&args[2], fails) {
            Ok(()) => "ok".to_owned(),
            Err(Failure::Body(reason) | Failure::Cleanup(reason)) => reason.to_owned(),
            Err(Failure::Both { body, cleanup }) => format!("both-errors:{body}+{cleanup}"),
        },
        _ => unreachable!(),
    });
    match observed {
        Ok(result) => event(&format!("result-{result}")),
        Err(_) => event("caught-panic"),
    }
}
