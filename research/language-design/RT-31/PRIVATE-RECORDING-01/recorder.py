"""Bounded SQLite recorder with a closed metadata and redacted-event schema."""
from contextlib import contextmanager
from dataclasses import dataclass
import json
import sqlite3

TYPES = ("tool-result", "diagnostic")
OUTCOMES = ("ok", "refused")
DIAGNOSTICS = ("stale-revision", "schema-rejected")
RETENTION = {"metadata": 20, "redacted": 10}
AUDIT_RETENTION = 30
WORKSPACES = (11, 22)
ACTORS = (1, 2, 3)

SCHEMA = """
CREATE TABLE permission (
    workspace INTEGER, actor INTEGER, action TEXT, epoch INTEGER, active INTEGER,
    PRIMARY KEY(workspace, actor, action)
);
CREATE TABLE event (
    id INTEGER PRIMARY KEY AUTOINCREMENT, workspace INTEGER, mode TEXT, kind TEXT,
    outcome TEXT, duration_ms INTEGER, body TEXT, expires INTEGER
);
CREATE TABLE audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, workspace INTEGER, actor INTEGER, action TEXT,
    outcome TEXT, expires INTEGER
);
"""


@dataclass(frozen=True)
class Grant:
    workspace: int
    actor: int
    action: str
    epoch: int


class Recorder:
    def __init__(self, path, create=False):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if create:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def configure(self, grant, active):
        """Install fixture authority state through the trusted administrative path."""
        with self.transaction():
            self.db.execute("""
                INSERT INTO permission VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(workspace, actor, action) DO UPDATE SET
                  epoch=excluded.epoch, active=excluded.active
            """, (grant.workspace, grant.actor, grant.action, grant.epoch, active))

    def allowed(self, grant, workspace, action):
        if grant.workspace != workspace or grant.action != action:
            return False
        row = self.db.execute(
            "SELECT epoch, active FROM permission WHERE workspace=? AND actor=? AND action=?",
            (workspace, grant.actor, action),
        ).fetchone()
        return row is not None and tuple(row) == (grant.epoch, 1)

    def note(self, grant, workspace, action, outcome, now):
        safe_workspace = workspace if workspace in WORKSPACES else None
        actor = grant.actor if grant.actor in ACTORS else None
        self.db.execute("INSERT INTO audit(workspace, actor, action, outcome, expires) VALUES (?,?,?,?,?)",
                        (safe_workspace, actor, action, outcome, now + AUDIT_RETENTION))

    def capture(self, grant, workspace, mode, now, kind, outcome, duration_ms, payload):
        if type(mode) is not str or mode not in RETENTION:
            return None
        action = "capture-" + mode
        with self.transaction():
            if not self.allowed(grant, workspace, action):
                self.note(grant, workspace, action, "denied", now)
                return None
            if (type(kind) is not str or kind not in TYPES
                    or type(outcome) is not str or outcome not in OUTCOMES
                    or type(duration_ms) is not int or not 0 <= duration_ms <= 10_000):
                self.note(grant, workspace, action, "schema-rejected", now)
                return None
            body = None
            if mode == "redacted":
                code = payload.get("diagnostic") if type(payload) is dict else None
                redacted = code if type(code) is str and code in DIAGNOSTICS else "redacted"
                body = json.dumps({"diagnostic": redacted}, separators=(",", ":"))
            row = self.db.execute("""
                INSERT INTO event(workspace,mode,kind,outcome,duration_ms,body,expires)
                VALUES (?,?,?,?,?,?,?)
            """, (workspace, mode, kind, outcome, duration_ms, body, now + RETENTION[mode]))
            self.note(grant, workspace, action, "captured", now)
            return row.lastrowid

    def export(self, grant, workspace, mode, now):
        if type(mode) is not str or mode not in RETENTION:
            return None
        action = "export-" + mode
        with self.transaction():
            if not self.allowed(grant, workspace, action):
                self.note(grant, workspace, action, "denied", now)
                return None
            rows = self.db.execute("""
                SELECT id,kind,outcome,duration_ms,body FROM event
                WHERE workspace=? AND expires>? ORDER BY id
            """, (workspace, now)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                body = item.pop("body")
                if mode == "redacted" and body is not None:
                    item["redacted"] = json.loads(body)
                result.append(item)
            self.note(grant, workspace, action, "exported", now)
            return result

    def delete(self, grant, workspace, event, now):
        with self.transaction():
            if not self.allowed(grant, workspace, "delete"):
                self.note(grant, workspace, "delete", "denied", now)
                return False
            row = self.db.execute("DELETE FROM event WHERE workspace=? AND id=?", (workspace, event))
            outcome = "deleted" if row.rowcount else "absent"
            self.note(grant, workspace, "delete", outcome, now)
            return row.rowcount == 1

    def purge(self, grant, workspace, now):
        with self.transaction():
            if not self.allowed(grant, workspace, "purge"):
                self.note(grant, workspace, "purge", "denied", now)
                return None
            deleted = self.db.execute("DELETE FROM event WHERE workspace=? AND expires<=?",
                                      (workspace, now)).rowcount
            audit_deleted = self.db.execute("DELETE FROM audit WHERE workspace=? AND expires<=?",
                                            (workspace, now)).rowcount
            self.note(grant, workspace, "purge", "purged", now)
            return deleted, audit_deleted

    def export_audit(self, grant, workspace, now):
        with self.transaction():
            if not self.allowed(grant, workspace, "audit"):
                self.note(grant, workspace, "audit", "denied", now)
                return None
            rows = self.db.execute("""
                SELECT actor, action, outcome FROM audit WHERE workspace=? AND expires>? ORDER BY id
            """, (workspace, now)).fetchall()
            self.note(grant, workspace, "audit", "exported", now)
            return [dict(row) for row in rows]
