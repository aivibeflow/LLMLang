"""Independent caller-obligation projection for Scenario 97 observations.

This module consumes recorded events and reconstructs ownership obligations.
It does not import or call the operational composition model.
"""
from __future__ import annotations


def audit_obligations(observation, required_resources, cleanup_budget):
    issues = []
    resources = tuple(required_resources)
    if len(set(resources)) != len(resources):
        return ("required cleanup resources are not unique",)
    if type(cleanup_budget) is not int or cleanup_budget < 0:
        return ("invalid cleanup budget supplied to audit",)

    trace = observation.cleanup_trace
    observed_names = tuple(event.resource for event in trace)
    if observed_names != resources:
        issues.append("cleanup trace does not cover required resources in declared order")
    owners = dict(observation.owners)
    states = dict(observation.resource_states)
    if len(owners) != len(observation.owners):
        issues.append("duplicate resource ownership entry")
    if len(states) != len(observation.resource_states):
        issues.append("duplicate resource state entry")

    expected_owners = {name: "callee" for name in resources}
    expected_states = {name: "live" for name in resources}
    used = 0
    blocked_seen = False
    all_cleanup_succeeded = True
    for event in trace:
        if not event.attempted:
            blocked_seen = True
            all_cleanup_succeeded = False
            if event.result is not None or event.disposition is not None:
                issues.append(f"blocked action {event.resource} reports a result")
            expected_owners[event.resource] = "callee_cleanup_debt"
            expected_states[event.resource] = "cleanup_blocked"
            continue
        used += 1
        if blocked_seen:
            issues.append("cleanup continued after a blocked action")
        if event.result == "ok" and event.disposition == "released":
            expected_owners.pop(event.resource, None)
            expected_states[event.resource] = "released"
        elif event.result in {"error", "panic"} and event.disposition == "retained":
            all_cleanup_succeeded = False
            expected_owners[event.resource] = "callee_cleanup_debt"
            expected_states[event.resource] = "retained_after_error"
        elif event.result in {"error", "panic"} and event.disposition == "consumed":
            all_cleanup_succeeded = False
            expected_owners.pop(event.resource, None)
            expected_states[event.resource] = "consumed_with_error"
        elif event.result in {"error", "panic"} and event.disposition == "indeterminate":
            all_cleanup_succeeded = False
            expected_owners[event.resource] = "indeterminate_cleanup_debt"
            expected_states[event.resource] = "indeterminate_after_error"
        else:
            issues.append(f"invalid result/disposition for {event.resource}")
            all_cleanup_succeeded = False
    if used != min(cleanup_budget, len(resources)):
        issues.append("attempt count does not match cleanup budget")

    if observation.owned_value:
        if observation.transfer_timing == "transfer_first":
            expected_owners["returned_value"] = "caller"
            expected_states["returned_value"] = "caller_owned"
        elif observation.transfer_timing == "stage_until_cleanup":
            if all_cleanup_succeeded:
                expected_owners["returned_value"] = "caller"
                expected_states["returned_value"] = "caller_owned"
            else:
                expected_owners["returned_value"] = "pending_return_cleanup_debt"
                expected_states["returned_value"] = "pending_with_cleanup_debt"
        else:
            issues.append("unknown owned-value transfer timing")

    if owners != expected_owners:
        issues.append(f"caller obligations mismatch: expected {expected_owners}, got {owners}")
    if states != expected_states:
        issues.append(f"resource states mismatch: expected {expected_states}, got {states}")
    return tuple(issues)
