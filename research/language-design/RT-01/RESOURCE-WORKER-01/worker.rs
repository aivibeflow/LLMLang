use std::fs::{self, File, OpenOptions};
use std::io::{self, BufRead, Write};
use std::os::fd::AsRawFd;
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::thread;

#[derive(Clone, Copy, PartialEq)]
enum Policy { Guarded, AdmissionOnly, EarlyTerminal }

impl Policy {
    fn parse(text: &str) -> Self {
        match text {
            "guarded" => Self::Guarded,
            "admission_only" => Self::AdmissionOnly,
            "early_terminal" => Self::EarlyTerminal,
            _ => panic!("unknown fixture policy"),
        }
    }
}

struct Job {
    file: Option<File>,
    path: PathBuf,
    readonly: bool,
    cancellation: bool,
    written: Option<&'static str>,
    settled: Option<&'static str>,
}

impl Job {
    fn new(path: PathBuf, readonly: bool) -> Self {
        Self { file: None, path, readonly, cancellation: false, written: None, settled: None }
    }

    fn perform(&mut self, command: &str, policy: Policy, byte: u8) -> (String, bool) {
        if let Some(value) = self.settled {
            return (format!("already_{value}"), false);
        }
        let mut released = false;
        let message = match command {
            "start" => {
                if self.cancellation {
                    "skipped".to_owned()
                } else {
                    assert!(self.file.is_none());
                    let file = OpenOptions::new().read(true).write(!self.readonly).open(&self.path).unwrap();
                    assert!(fs::symlink_metadata(fd_path(file.as_raw_fd())).is_ok());
                    self.file = Some(file);
                    "started".to_owned()
                }
            }
            "cancel" => {
                if self.written.is_some() && policy != Policy::EarlyTerminal {
                    "too_late".to_owned()
                } else {
                    self.cancellation = true;
                    if policy == Policy::EarlyTerminal { "early_cancelled" } else { "requested" }.to_owned()
                }
            }
            "write" => {
                if self.cancellation && policy != Policy::AdmissionOnly {
                    "blocked".to_owned()
                } else if let Some(file) = self.file.as_mut() {
                    assert!(self.written.is_none());
                    match file.write_all(&[byte]) {
                        Ok(()) => { self.written = Some("ok"); "written".to_owned() }
                        Err(error) => {
                            assert_eq!(error.raw_os_error(), Some(9));
                            self.written = Some("io_failure");
                            "write_failed".to_owned()
                        }
                    }
                } else {
                    "blocked".to_owned()
                }
            }
            "settle" => {
                if let Some(file) = self.file.take() {
                    let fd = file.as_raw_fd();
                    drop(file);
                    assert_eq!(fs::symlink_metadata(fd_path(fd)).unwrap_err().kind(), io::ErrorKind::NotFound);
                    released = true;
                }
                let terminal = if self.cancellation { "cancelled" } else { self.written.unwrap() };
                self.settled = Some(terminal);
                format!("settled_{terminal}")
            }
            _ => panic!("unknown fixture command"),
        };
        (message, released)
    }
}

fn fd_path(fd: i32) -> PathBuf { PathBuf::from(format!("/proc/self/fd/{fd}")) }

struct Command {
    client: usize,
    target: usize,
    kind: String,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let root = Path::new(&args[1]);
    let policy = Policy::parse(&args[2]);
    let mask: u8 = args[3].parse().unwrap();
    let mut jobs = [
        Job::new(root.join("job-0"), mask & 1 != 0),
        Job::new(root.join("job-1"), mask & 2 != 0),
    ];
    let (requests, work) = mpsc::sync_channel::<Command>(0);
    let (replies, result) = mpsc::sync_channel::<String>(0);
    let worker = thread::spawn(move || {
        for command in work {
            let (event, released) = jobs[command.target].perform(
                &command.kind, policy, b'A' + command.target as u8
            );
            let active = [jobs[0].file.is_some(), jobs[1].file.is_some()].map(u8::from);
            replies.send(format!("step {} {} {event} {}{} {}", command.client, command.target,
                                 active[0], active[1], u8::from(released))).unwrap();
        }
        assert!(jobs.iter().all(|task| task.file.is_none()));
        replies.send(format!("final {} {}", jobs[0].settled.unwrap(), jobs[1].settled.unwrap())).unwrap();
    });
    let mut clients = Vec::new();
    let mut senders = Vec::new();
    for _ in 0..2 {
        let (dispatch, receive) = mpsc::sync_channel(0);
        let to_worker = requests.clone();
        clients.push(thread::spawn(move || {
            for command in receive {
                to_worker.send(command).unwrap();
            }
        }));
        senders.push(dispatch);
    }
    drop(requests);
    for row in io::stdin().lock().lines() {
        let encoded = row.unwrap();
        let parts: Vec<&str> = encoded.split_ascii_whitespace().collect();
        let client: usize = parts[0].parse().unwrap();
        senders[client].send(Command {
            client, target: parts[1].parse().unwrap(), kind: parts[2].to_owned(),
        }).unwrap();
        println!("{}", result.recv().unwrap());
    }
    drop(senders);
    for client in clients { client.join().unwrap(); }
    println!("{}", result.recv().unwrap());
    worker.join().unwrap();
}
