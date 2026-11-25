"""Check redaction before native SQLite insertion, scoped lifecycle and audit."""
import argparse
import base64
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from recorder import Grant, Recorder, WORKSPACES

MODES = ("metadata", "redacted")
ACTIONS = {"capture-metadata": 1, "capture-redacted": 1, "export-metadata": 2,
           "export-redacted": 2, "delete": 2, "purge": 3, "audit": 3}


def configure(service):
    grants = {(workspace, action): Grant(workspace, actor, action, 1)
              for workspace in WORKSPACES for action, actor in ACTIONS.items()}
    for grant in grants.values():
        service.configure(grant, active=True)
    return grants


def capture_corpus(service, grants):
    raw = []
    identifiers = {}
    for workspace in WORKSPACES:
        ids = {}
        for mode in MODES:
            ids[mode] = []
            for ordinal in range(6):
                marker = f"SYNTHETIC-PRIVATE-{workspace}-{mode}-{ordinal}"
                alias = base64.b64encode(marker.encode()).decode()
                raw.extend((marker.encode(), alias.encode()))
                value = "stale-revision" if ordinal == 0 else (alias if ordinal == 1 else marker)
                captured = service.capture(
                    grants[(workspace, "capture-" + mode)], workspace, mode, 100,
                    "diagnostic", "ok", ordinal,
                    {"diagnostic": value, "message": marker, "nested": {"token": alias},
                     marker: marker},
                )
                assert type(captured) is int
                ids[mode].append(captured)
        identifiers[workspace] = ids
    return tuple(raw), identifiers


def run(path):
    service = Recorder(path, create=True)
    authority = Recorder(path)
    assert service.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    sql = []
    service.db.set_trace_callback(sql.append)
    authority.db.set_trace_callback(sql.append)
    try:
        grants = configure(service)
        markers, identifiers = capture_corpus(service, grants)

        def grant(action, workspace=11):
            return grants[(workspace, action)]

        local = identifiers[11]
        peer = identifiers[22]
        redacted = service.export(grant("export-redacted"), 11, "redacted", 101)
        expected_ids = set(local["metadata"] + local["redacted"])
        assert {row["id"] for row in redacted} == expected_ids
        assert not expected_ids & set(peer["metadata"] + peer["redacted"])
        bodies = [row["redacted"]["diagnostic"] for row in redacted if "redacted" in row]
        assert bodies == ["stale-revision"] + ["redacted"] * 5
        metadata = service.export(grant("export-metadata"), 11, "metadata", 101)
        assert {row["id"] for row in metadata} == expected_ids
        assert all("redacted" not in row for row in metadata)
        checks = {
            "export_other_workspace": service.export(grant("export-redacted"), 22, "redacted", 101) is None,
            "metadata_grant_cannot_export_redacted": service.export(
                grant("export-metadata"), 11, "redacted", 101) is None,
            "metadata_grant_cannot_capture_redacted": service.capture(
                grant("capture-metadata"), 11, "redacted", 101, "diagnostic", "ok", 0, {}) is None,
            "delete_other_event": not service.delete(grant("delete"), 11, peer["metadata"][0], 101),
            "other_workspace_still_readable": len(service.export(
                grant("export-redacted", 22), 22, "redacted", 101)) == 12,
        }
        checks["delete_exact_event"] = service.delete(grant("delete"), 11, local["metadata"][0], 102)
        checks["repeat_delete"] = not service.delete(grant("delete"), 11, local["metadata"][0], 102)
        visible = service.export(grant("export-redacted"), 11, "redacted", 102)
        checks["deleted_event_absent"] = {row["id"] for row in visible} == expected_ids - {local["metadata"][0]}

        probe_marker = "SYNTHETIC-INVALID-METADATA"
        markers += (probe_marker.encode(),)
        checks["unrecognized_metadata"] = service.capture(
            grant("capture-redacted"), 11, "redacted", 102, probe_marker, "ok", 1, {}) is None
        checks["raw_capture_mode_refused"] = service.capture(
            grant("capture-redacted"), 11, "raw", 102, "diagnostic", "ok", 1,
            {"diagnostic": probe_marker}) is None
        checks["malformed_duration"] = service.capture(
            grant("capture-redacted"), 11, "redacted", 102, "diagnostic", "ok", True, {}) is None
        old_grant = grant("capture-redacted")
        replacement = replace(old_grant, epoch=2)
        authority.configure(replacement, active=False)
        checks["revoked_capture"] = service.capture(
            old_grant, 11, "redacted", 103, "diagnostic", "ok", 1, {}) is None
        authority.configure(replacement, active=True)
        checks["stale_epoch_after_reactivation"] = service.capture(
            old_grant, 11, "redacted", 104, "diagnostic", "ok", 1, {}) is None
        refreshed_event = service.capture(replacement, 11, "redacted", 104, "diagnostic", "ok", 1, {})
        checks["current_epoch"] = type(refreshed_event) is int

        authority.configure(replace(grant("export-redacted"), epoch=2), active=False)
        checks["revoked_export"] = service.export(grant("export-redacted"), 11, "redacted", 104) is None
        still_metadata = service.export(grant("export-metadata"), 11, "metadata", 110)
        active_ids = set(local["metadata"][1:] + [refreshed_event])
        checks["redacted_expiry_before_purge"] = {row["id"] for row in still_metadata} == active_ids
        checks["purge_expired_scope"] = service.purge(grant("purge"), 11, 110) == (6, 0)
        remaining = service.db.execute("SELECT count(*) FROM event WHERE workspace=22").fetchone()[0]
        checks["purge_preserves_peer"] = remaining == 12
        checks["metadata_expiry"] = service.export(grant("export-metadata"), 11, "metadata", 120) == []
        audit = service.export_audit(grant("audit"), 11, 121)
        checks["audit_projection"] = all(set(row) == {"actor", "action", "outcome"} for row in audit)
        checks["audit_denied"] = service.export_audit(grant("export-metadata"), 11, 121) is None
        checks["audit_retention"] = all(
            row["action"] not in ("capture-redacted", "capture-metadata")
            for row in service.export_audit(grant("audit"), 11, 135))
        checks["expired_audit_rows_deleted"] = service.purge(grant("purge"), 11, 135)[1] > 0

        with_sql = "\n".join(sql).encode()
        rendered = json.dumps([redacted, metadata, audit]).encode()
        files = [path.read_bytes(), Path(str(path) + "-wal").read_bytes()]
        assert all(marker not in candidate for marker in markers for candidate in [with_sql, rendered, *files])
        assert all(checks.values()), checks
        count = service.db.execute("SELECT count(*) FROM audit").fetchone()[0]
    finally:
        authority.close()
        service.close()
    assert all(marker not in path.read_bytes() for marker in markers)
    return {
        "sqlite": sqlite3.sqlite_version,
        "input_cases": 24,
        "payload_canaries": len(markers),
        "initial_restricted_exports": {"redacted": redacted, "metadata": metadata},
        "active_audit_rows_after_purge": count,
        "controls": checks,
        "canaries_absent_from": ["SQL trace", "export views", "SQLite database", "active WAL", "checkpointed database"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="llmlang-private-recording-") as directory:
        evidence = run(Path(directory) / "recording.db")
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
