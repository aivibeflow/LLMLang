"""Reconstruct a controlled reading of a typed release contract on stdin."""
import json
import sys


def render(model):
    matching = ", ".join(model["grant_binding"])
    receipt = ", ".join(model["receipt_binding"])
    return (
        f"R01 New release requires a {model['new_grant_role']} grant matching {matching}.\n"
        f"R02 Existing receipt requires a {model['retry_grant_role']} grant matching {matching}. "
        f"Replay requires exact {receipt} and emits no new release.\n"
        f"R03 Retry checks follow {model['disclosure_order']}. Denial or conflict emits no release.\n"
        f"R04 Grant epoch comes from {model['epoch_source']}.\n"
    )


if __name__ == "__main__":
    sys.stdout.write(render(json.load(sys.stdin)))
