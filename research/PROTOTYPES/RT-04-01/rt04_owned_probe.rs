// Standard-library-only runtime for the bounded COR-13 source fixture.
use std::io::{self, BufRead};

// @CHECKED_CALLER@

#[derive(Clone, Copy, PartialEq, Eq)]
enum Disposition {
    Ok,
    RetainedError,
    ConsumedError,
    Indeterminate,
}

impl Disposition {
    fn parse(value: &str) -> Self {
        match value {
            "ok" => Self::Ok,
            "retained_error" => Self::RetainedError,
            "consumed_error" => Self::ConsumedError,
            "indeterminate" => Self::Indeterminate,
            _ => panic!("unknown fixture disposition {value}"),
        }
    }

    fn label(self) -> &'static str {
        match self {
            Self::Ok => "ok",
            Self::RetainedError => "retained_error",
            Self::ConsumedError => "consumed_error",
            Self::Indeterminate => "indeterminate",
        }
    }
}

#[derive(Clone, Copy)]
struct Roles(u8, u8);

impl Roles {
    fn permits(self, prior: Option<Self>) -> bool {
        self.0 != self.1
            && prior.is_none_or(|held| held.1 != self.0 && held.1 != self.1 && held.0 != self.1)
    }
}

struct Handle(Roles);

impl Handle {
    fn close(self, trace: &mut Trace, slot: &'static str, disposition: Disposition) -> HandleState {
        trace.release(slot, disposition);
        match disposition {
            Disposition::Ok | Disposition::ConsumedError => HandleState::Absent,
            Disposition::RetainedError => HandleState::Usable(self, Usable::Retained),
            Disposition::Indeterminate => HandleState::Reconcile(self.0),
        }
    }
}

enum Usable {
    Owned,
    Retained,
}

enum HandleState {
    Usable(Handle, Usable),
    Reconcile(Roles),
    Absent,
}

impl HandleState {
    fn obligation(&self) -> Option<&'static str> {
        match self {
            Self::Usable(_, Usable::Owned) => Some("owned"),
            Self::Usable(_, Usable::Retained) => Some("retained"),
            Self::Reconcile(_) => Some("reconcile"),
            Self::Absent => None,
        }
    }

    fn reservation(&self) -> Option<Roles> {
        match self {
            Self::Usable(handle, _) => Some(handle.0),
            Self::Reconcile(roles) => Some(*roles),
            Self::Absent => None,
        }
    }
}

#[derive(Default)]
struct Trace {
    tag: &'static str,
    returned: String,
    events: Vec<[&'static str; 3]>,
    domain_error: bool,
    errors: Vec<[&'static str; 2]>,
    second: &'static str,
    reservations: Vec<(&'static str, Roles)>,
    forwarded: String,
}

impl Trace {
    fn event(&mut self, kind: &'static str, slot: &'static str, value: &'static str) {
        self.events.push([kind, slot, value]);
    }

    fn release(&mut self, slot: &'static str, disposition: Disposition) {
        self.event("release", slot, disposition.label());
        if disposition != Disposition::Ok {
            self.errors.push([slot, disposition.label()]);
        }
    }

    fn encode(self) -> String {
        let reservations = self.reservations.iter().map(|(slot, roles)| {
            format!("{slot},{},{}", char::from(roles.0), char::from(roles.1))
        });
        [
            self.tag.to_string(),
            self.returned,
            self.events.iter().map(|event| event.join(",")).collect::<Vec<_>>().join(";"),
            u8::from(self.domain_error).to_string(),
            self.errors.iter().map(|error| error.join(",")).collect::<Vec<_>>().join(";"),
            self.second.to_string(),
            reservations.collect::<Vec<_>>().join(";"),
            self.forwarded,
        ]
        .join("|")
    }
}

fn obligations(handle: &HandleState, scratch: Option<&str>) -> String {
    [("handle", handle.obligation()), ("local", scratch)]
        .into_iter()
        .filter_map(|(slot, kind)| kind.map(|kind| format!("{slot},{kind}")))
        .collect::<Vec<_>>()
        .join(";")
}

fn run(row: &str) -> Trace {
    let fields: [&str; 8] = row.split(',').collect::<Vec<_>>().try_into().expect("expected eight fields");
    let ids = [fields[0], fields[1], fields[2], fields[3]].map(|value| value.as_bytes()[0]);
    let first = Roles(ids[FIRST[0]], ids[FIRST[1]]);
    let second = Roles(ids[SECOND[0]], ids[SECOND[1]]);
    let mut trace = Trace { second: "not_reached", ..Trace::default() };
    if !first.permits(None) {
        trace.event("check", "handle", "refused");
        return trace;
    }

    trace.event("check", "handle", "ok");
    trace.event("acquire", "handle", "ok");
    trace.event("acquire", "local", "ok");
    let wants_value = fields[4] == "1";
    let local_close = Disposition::parse(fields[5]);
    let handle_close = Disposition::parse(fields[6]);
    let caller_close = Disposition::parse(fields[7]);
    let handle = Handle(first);
    let moved_early = EARLY_TRANSFER && wants_value;

    if moved_early {
        trace.event("transfer", "handle", "ok");
    }
    trace.release("local", local_close);
    let scratch = match local_close {
        Disposition::RetainedError => Some("retained"),
        Disposition::Indeterminate => Some("reconcile"),
        Disposition::Ok | Disposition::ConsumedError => None,
    };
    let handle = if moved_early {
        HandleState::Usable(handle, Usable::Owned)
    } else if wants_value && local_close == Disposition::Ok {
        trace.event("transfer", "handle", "ok");
        HandleState::Usable(handle, Usable::Owned)
    } else {
        handle.close(&mut trace, "handle", handle_close)
    };
    trace.domain_error = !wants_value;
    let tag = match (wants_value, trace.errors.is_empty(), moved_early) {
        (false, true, _) => "Err",
        (false, false, _) => "ErrWithCleanupErrors",
        (true, true, _) => "OkWithValue",
        (true, false, true) => "CleanupFailedWithValue",
        (true, false, false) => "StagedCleanupFailedWithoutValue",
    };
    trace.tag = tag;
    trace.returned = obligations(&handle, scratch);

    let after = handle_result(&mut trace, tag, handle, caller_close);
    trace.forwarded = obligations(&after, scratch);
    let prior = after.reservation();
    if let Some(roles) = prior {
        trace.reservations.push(("handle", roles));
    }
    if second.permits(prior) {
        trace.event("check", "second", "ok");
        trace.event("acquire", "second", "ok");
        trace.reservations.push(("second", second));
        trace.second = "started";
    } else {
        trace.event("check", "second", "refused");
        trace.second = "refused";
    }
    trace
}

fn main() -> io::Result<()> {
    for line in io::stdin().lock().lines() {
        println!("{}", run(&line?).encode());
    }
    Ok(())
}
