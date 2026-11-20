"""Execute the shared workload with direct state transitions."""

from rt04_backup_roles import BackupPair
from rt04_owned_call_match import Obligation, ResultCase
from rt04_return_disposition import TransferTiming
from rt04_shared_owned_workload import Inputs, Trace, Workload


def execute(workload: Workload, timing: TransferTiming, inputs: Inputs) -> Trace:
    a, b, c, d = inputs.identities
    values = {"a": a, "b": b, "c": c, "d": d}
    owner = values[workload.first.source]
    target = values[workload.first.destination]
    if owner == target:
        return Trace(None, (("check", "handle", "refused"),), False, (), "not_reached", ())

    events = [("check", "handle", "ok"), ("acquire", "handle", "ok"), ("acquire", "local", "ok")]
    errors = []
    obligations = set()

    def release(slot, disposition):
        events.append(("release", slot, disposition))
        if disposition != "ok":
            errors.append((slot, disposition))
        if disposition == "retained_error":
            obligations.add(Obligation(slot, "retained"))
        elif disposition == "indeterminate":
            obligations.add(Obligation(slot, "reconcile"))

    def transfer():
        events.append(("transfer", "handle", "ok"))
        obligations.add(Obligation("handle", "owned"))

    early = inputs.wants_value and timing == "before_cleanup"
    if early:
        transfer()
    release("local", inputs.local_close)
    if not early:
        if inputs.wants_value and inputs.local_close == "ok":
            transfer()
        else:
            release("handle", inputs.handle_close)

    if not inputs.wants_value:
        tag = "ErrWithCleanupErrors" if errors else "Err"
    elif not errors:
        tag = "OkWithValue"
    else:
        tag = "CleanupFailedWithValue" if early else "StagedCleanupFailedWithoutValue"

    reservations = []
    retained = any(obligation.slot == "handle" for obligation in obligations)
    if retained:
        reservations.append(("handle", BackupPair(owner, target)))
    new_source = values[workload.second.source]
    new_target = values[workload.second.destination]
    overlap = target in (new_source, new_target) or new_target == owner
    if new_source == new_target or (retained and overlap):
        events.append(("check", "second", "refused"))
        proposal = "refused"
    else:
        events.extend((("check", "second", "ok"), ("acquire", "second", "ok")))
        reservations.append(("second", BackupPair(new_source, new_target)))
        proposal = "started"
    return Trace(ResultCase(tag, frozenset(obligations)), tuple(events), not inputs.wants_value,
                 tuple(errors), proposal, tuple(reservations))
