"""Read only typed clauses from standard input and render controlled prose."""

import json
import sys


def render(clause):
    identifier = clause["id"]
    scope, condition = clause["scope"], clause["condition"]
    mode, action = clause["mode"], clause["action"]
    origin, deadline = clause["origin"], clause["deadline"]
    if scope not in {"retail", "wholesale", "all"} or condition not in {"succeeded", "failed"}:
        raise ValueError("unsupported scope or reservation outcome")
    if mode not in {"require", "forbid"} or action not in {"confirmation", "notification"}:
        raise ValueError("unsupported deontic mode or action")
    if origin is None and deadline is None:
        window = "throughout the observed interval"
    elif origin in {"payment registration", "reservation observation"} and type(deadline) is int and 0 <= deadline <= 7:
        window = f"from {origin} through {deadline} seconds after it, inclusive"
    else:
        raise ValueError("unsupported observation window")
    subject = "all orders" if scope == "all" else f"{scope} orders"
    return f"[{identifier}] For {subject} when reservation {condition}, {mode} {action} {window}."


def main():
    clauses = json.load(sys.stdin)
    try:
        lines = [render(clause) for clause in clauses]
    except (ValueError, KeyError) as error:
        print(json.dumps({"status": "UNKNOWN", "reason": str(error)}))
    else:
        print(json.dumps({"status": "RECONSTRUCTED", "lines": lines}))


if __name__ == "__main__":
    main()
