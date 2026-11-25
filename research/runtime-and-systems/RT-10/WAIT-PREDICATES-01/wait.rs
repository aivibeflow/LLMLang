use std::sync::{mpsc, Arc, Condvar, Mutex};
use std::thread;
use std::time::Duration;

#[derive(Default)]
struct Observation {
    phase: u8,
    item: Option<u8>,
    cancelled: bool,
}

#[derive(Clone, Copy)]
enum Policy {
    WakeMeansWork,
    CancelFirst,
    WorkFirst,
}

type Shared = (Mutex<Observation>, Condvar);

fn waiter(shared: &Shared, waiting: mpsc::Sender<u8>, policy: Policy) -> &'static str {
    let (state, condition) = shared;
    let mut state = state.lock().unwrap();
    loop {
        if matches!(policy, Policy::WakeMeansWork) {
            waiting.send(state.phase).unwrap();
            state = condition.wait(state).unwrap();
            return if state.item.take().is_some() { "work" } else { "empty-reported-as-work" };
        }
        if state.cancelled && (matches!(policy, Policy::CancelFirst) || state.item.is_none()) {
            return "cancelled";
        }
        if state.item.take().is_some() {
            return "work";
        }
        waiting.send(state.phase).unwrap();
        state = condition.wait(state).unwrap();
    }
}

fn change(shared: &Shared, phase: u8, item: bool, cancelled: bool) {
    let (state, condition) = shared;
    let mut state = state.lock().unwrap();
    state.phase = phase;
    state.item = item.then_some(7);
    state.cancelled = cancelled;
    condition.notify_one();
}

fn await_wait(receiver: &mpsc::Receiver<u8>, phase: u8) {
    loop {
        if receiver.recv_timeout(Duration::from_secs(3)).unwrap() == phase {
            return;
        }
    }
}

fn main() {
    let scenario = std::env::args().nth(1).expect("scenario");
    let policy = match scenario.as_str() {
        "pulse-only" => Policy::WakeMeansWork,
        "both-work-first" => Policy::WorkFirst,
        _ => Policy::CancelFirst,
    };
    let shared = Arc::new((Mutex::new(Observation::default()), Condvar::new()));
    let (sender, receiver) = mpsc::channel();
    if scenario == "already-published" {
        change(&shared, 1, true, false);
    }
    let scope = Arc::clone(&shared);
    let child = thread::spawn(move || waiter(&scope, sender, policy));
    if scenario != "already-published" {
        await_wait(&receiver, 0);
    }
    let mut returned_to_wait = false;
    match scenario.as_str() {
        "pulse-only" => change(&shared, 1, false, false),
        "pulse-then-work" => {
            change(&shared, 1, false, false);
            await_wait(&receiver, 1);
            returned_to_wait = true;
            change(&shared, 2, true, false);
        }
        "cancel-only" => change(&shared, 1, false, true),
        "both-cancel-first" | "both-work-first" => change(&shared, 1, true, true),
        "already-published" => (),
        _ => panic!("unknown scenario"),
    }
    let outcome = child.join().unwrap();
    let final_state = shared.0.lock().unwrap();
    println!("{outcome}:{}:{}:{}", final_state.item.is_some(), final_state.cancelled, returned_to_wait);
}
