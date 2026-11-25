use std::cell::RefCell;
use std::future::Future;
use std::pin::Pin;
use std::rc::Rc;
use std::task::{Context, Poll, Waker};

#[derive(Default)]
struct Tracker {
    live: u8,
    events: Vec<String>,
}

type Shared = Rc<RefCell<Tracker>>;

struct Guard {
    id: &'static str,
    bit: u8,
    active: bool,
    diagnostic: bool,
    tracker: Shared,
}

impl Guard {
    fn acquire(tracker: &Shared, id: &'static str, bit: u8, failure: u8, mask: u8)
        -> Result<Self, &'static str>
    {
        let mut state = tracker.borrow_mut();
        if failure == bit {
            state.events.push(format!("acquire-failed:{id}"));
            return Err(id);
        }
        assert_eq!(state.live & bit, 0);
        state.live |= bit;
        state.events.push(format!("acquire:{id}"));
        Ok(Self { id, bit, active: true, diagnostic: mask & bit != 0, tracker: Rc::clone(tracker) })
    }

    fn release(&mut self, mode: &str) -> Option<&'static str> {
        assert!(self.active);
        let mut state = self.tracker.borrow_mut();
        assert_ne!(state.live & self.bit, 0);
        state.live &= !self.bit;
        self.active = false;
        let status = if self.diagnostic { "diagnostic" } else { "ok" };
        state.events.push(format!("{mode}:{}:{status}", self.id));
        self.diagnostic.then_some(self.id)
    }

    fn close(mut self) -> Option<&'static str> {
        self.release("close")
    }
}

impl Drop for Guard {
    fn drop(&mut self) {
        if self.active {
            self.release("drop");
        }
    }
}

struct Checkpoint(bool);

impl Future for Checkpoint {
    type Output = ();

    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        if self.0 {
            return Poll::Ready(());
        }
        self.0 = true;
        cx.waker().wake_by_ref();
        Poll::Pending
    }
}

fn outcome(label: &str, diagnostics: &[Option<&str>]) -> String {
    let reported: Vec<_> = diagnostics.iter().flatten().copied().collect();
    format!("{label}/{}", reported.join(","))
}

async fn handle(tracker: &Shared, failure: u8, diagnostics: u8, explicit: bool) -> String {
    let a = match Guard::acquire(tracker, "A", 1, failure, diagnostics) {
        Ok(resource) => resource,
        Err(error) => return outcome(&format!("acquire:{error}"), &[]),
    };
    Checkpoint(false).await;
    let b = match Guard::acquire(tracker, "B", 2, failure, diagnostics) {
        Ok(resource) => resource,
        Err(error) => {
            return if explicit {
                outcome(&format!("acquire:{error}"), &[a.close()])
            } else {
                outcome(&format!("acquire:{error}"), &[])
            };
        }
    };
    Checkpoint(false).await;
    if explicit {
        outcome("completed", &[b.close(), a.close()])
    } else {
        outcome("completed", &[])
    }
}

fn main() {
    for polls in 0..4 {
        for failure in 0..3 {
            for diagnostics in 0..4 {
                for explicit in [false, true] {
                    let tracker = Rc::new(RefCell::new(Tracker::default()));
                    let mut future = Box::pin(handle(&tracker, failure, diagnostics, explicit));
                    let mut context = Context::from_waker(Waker::noop());
                    let mut result = String::from("cancelled");
                    for _ in 0..polls {
                        if let Poll::Ready(state) = future.as_mut().poll(&mut context) {
                            result = state;
                            break;
                        }
                    }
                    drop(future);
                    let state = tracker.borrow();
                    assert_eq!(state.live, 0u8);
                    println!("{polls} {failure} {diagnostics} {} | {result} | {}",
                             u8::from(explicit), state.events.join(","));
                }
            }
        }
    }
}
