"""Source-based oracle for a finite authorization and immutable receipt fixture."""

READING = (
    "R01 New release requires a release grant matching principal, workspace, artifact, revision, epoch.\n"
    "R02 Existing receipt requires a observe grant matching principal, workspace, artifact, revision, epoch. "
    "Replay requires exact operation, workspace, artifact, revision, payload and emits no new release.\n"
    "R03 Retry checks follow authority-before-conflict. Denial or conflict emits no release.\n"
    "R04 Grant epoch comes from decision-current.\n"
)


def from_source(request, principal, epoch, grant, prior):
    valid_binding = (grant is not None and grant["principal"] == principal
                     and grant["workspace"] == request["workspace"]
                     and grant["artifact"] == request["artifact"]
                     and grant["revision"] == request["revision"]
                     and grant["epoch"] == epoch)
    if prior is None:
        return "released" if valid_binding and grant["role"] == "release" else "denied"
    if not valid_binding or grant["role"] != "observe":
        return "denied"
    return "replayed" if (prior["operation"], prior["workspace"], prior["artifact"],
                          prior["revision"], prior["payload"]) == (
                              request["operation"], request["workspace"], request["artifact"],
                              request["revision"], request["payload"],
                          ) else "conflict"
