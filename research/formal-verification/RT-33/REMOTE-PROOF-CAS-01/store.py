"""SQLite metadata and bounded loopback delivery for the proof CAS fixture."""
import base64
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from secrets import token_urlsafe
import sqlite3
from threading import RLock, Thread

SCHEMA = """
CREATE TABLE payload (address TEXT PRIMARY KEY, body BLOB NOT NULL);
CREATE TABLE policy (project TEXT PRIMARY KEY, epoch INTEGER NOT NULL);
CREATE TABLE reader (project TEXT NOT NULL REFERENCES policy, audience TEXT NOT NULL,
                     PRIMARY KEY(project, audience));
CREATE TABLE candidate (project TEXT NOT NULL REFERENCES policy, claim TEXT NOT NULL,
                        address TEXT NOT NULL REFERENCES payload, epoch INTEGER NOT NULL,
                        message BLOB NOT NULL, signature BLOB NOT NULL,
                        PRIMARY KEY(project, claim, address, epoch));
CREATE TABLE lease (id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES policy,
                    claim TEXT NOT NULL, audience TEXT NOT NULL, address TEXT NOT NULL REFERENCES payload,
                    epoch INTEGER NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE clock (slot INTEGER PRIMARY KEY CHECK(slot = 0), ticks INTEGER NOT NULL);
"""
MAX_PAYLOAD = 256
PRODUCERS = {"alpha": {"alice", "bob"}, "beta": {"bob"}}


def digest(data):
    return sha256(data).hexdigest()


class Refusal(ValueError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status
        self.reason = reason


class Storage:
    def __init__(self, path, signers, checked, *, setup=True):
        self.path = path
        self.signers = signers
        self.checked = checked
        self.lock = RLock()
        if setup:
            with self.transaction() as db:
                db.executescript(SCHEMA)
                db.execute("INSERT INTO policy VALUES ('alpha', 1), ('beta', 1)")
                db.execute("INSERT INTO reader VALUES ('alpha', 'reader-a'), ('beta', 'reader-b')")
                db.execute("INSERT INTO clock VALUES (0, 0)")

    @contextmanager
    def transaction(self):
        with self.lock:
            db = sqlite3.connect(self.path)
            db.execute("PRAGMA foreign_keys = ON")
            try:
                with db:
                    yield db
            finally:
                db.close()

    def epoch(self, db, project, audience):
        row = db.execute("""SELECT epoch FROM policy JOIN reader USING(project)
                            WHERE project = ? AND audience = ?""", (project, audience)).fetchone()
        if row is None:
            raise Refusal(403, "not-authorized")
        return row[0]

    def publish(self, signed, exact_bytes):
        subject = json.loads(signed.message)
        project, issuer = subject["project"], subject["issuer"]
        if (project not in PRODUCERS or issuer not in PRODUCERS[project]
                or digest(exact_bytes) != subject["address"] or len(exact_bytes) > MAX_PAYLOAD):
            raise Refusal(403, "publisher-or-payload")
        with self.transaction() as db:
            if not self.signers.verify(signed, issuer):
                raise Refusal(403, "publisher-or-payload")
            epoch = db.execute("SELECT epoch FROM policy WHERE project = ?", (project,)).fetchone()[0]
            if subject["epoch"] != epoch:
                raise Refusal(403, "stale-publication-policy")
            if (project, subject["claim"], subject["address"]) not in self.checked:
                raise Refusal(422, "no-independent-check")
            db.execute("INSERT OR IGNORE INTO payload VALUES (?, ?)", (subject["address"], exact_bytes))
            db.execute("""INSERT OR IGNORE INTO candidate VALUES (?, ?, ?, ?, ?, ?)""",
                       (project, subject["claim"], subject["address"], epoch,
                        signed.message, signed.signature))

    def issue(self, project, claim, audience):
        with self.transaction() as db:
            epoch = self.epoch(db, project, audience)
            rows = db.execute("""SELECT address, message, signature FROM candidate
                                 WHERE project = ? AND claim = ? AND epoch = ? ORDER BY address""",
                              (project, claim, epoch)).fetchall()
            if not rows:
                raise Refusal(404, "candidate-unavailable")
            if len(rows) != 1:
                raise Refusal(409, "authorized-conflict")
            address, message, signature = rows[0]
            handle = token_urlsafe(24)
            now = db.execute("SELECT ticks FROM clock WHERE slot = 0").fetchone()[0]
            db.execute("INSERT INTO lease VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (handle, project, claim, audience, address, epoch, now + 4))
        return {"lease": handle, "receipt": message.decode(),
                "signature": base64.b64encode(signature).decode()}

    def read(self, db, handle, audience):
        row = db.execute("""SELECT project, claim, lease.address, epoch, expires, body
                            FROM lease JOIN payload USING(address)
                            WHERE id = ? AND audience = ?""", (handle, audience)).fetchone()
        if row is None:
            raise Refusal(403, "lease-unavailable")
        project, claim, address, epoch, expiry, body = row
        now = db.execute("SELECT ticks FROM clock WHERE slot = 0").fetchone()[0]
        if expiry <= now or self.epoch(db, project, audience) != epoch:
            raise Refusal(403, "lease-unavailable")
        total = db.execute("""SELECT COUNT(*) FROM candidate WHERE project = ? AND claim = ?
                             AND epoch = ?""", (project, claim, epoch)).fetchone()[0]
        if total > 1:
            raise Refusal(409, "authorized-conflict")
        if len(body) > MAX_PAYLOAD or digest(body) != address:
            raise Refusal(409, "payload-integrity")
        return address, body

    def preflight(self, handle, audience):
        with self.transaction() as db:
            return self.read(db, handle, audience)

    def deliver(self, handle, audience, captured, send):
        # Revocation and GC serialize with this bounded response.
        with self.transaction() as db:
            latest = self.read(db, handle, audience)
            if latest != captured:
                raise Refusal(409, "payload-changed")
            address, body = latest
            send(200, body, "application/octet-stream", address)

    def remove_candidate(self, project, claim):
        with self.transaction() as db:
            db.execute("DELETE FROM candidate WHERE project = ? AND claim = ?", (project, claim))

    def release(self, handle):
        with self.transaction() as db:
            db.execute("DELETE FROM lease WHERE id = ?", (handle,))

    def revoke(self, project, audience):
        with self.transaction() as db:
            db.execute("UPDATE policy SET epoch = epoch + 1 WHERE project = ?", (project,))
            db.execute("DELETE FROM reader WHERE project = ? AND audience = ?", (project, audience))

    def restore(self, project, audience):
        with self.transaction() as db:
            db.execute("INSERT INTO reader VALUES (?, ?)", (project, audience))

    def advance(self, ticks):
        with self.transaction() as db:
            db.execute("UPDATE clock SET ticks = ticks + ? WHERE slot = 0", (ticks,))

    def collect(self):
        with self.transaction() as db:
            db.execute("""DELETE FROM lease WHERE expires <= (SELECT ticks FROM clock WHERE slot = 0) OR
                          NOT EXISTS (SELECT 1 FROM policy JOIN reader USING(project)
                            WHERE policy.project = lease.project AND policy.epoch = lease.epoch
                            AND reader.audience = lease.audience)""")
            removed = db.execute("""DELETE FROM payload
                                    WHERE NOT EXISTS (SELECT 1 FROM candidate WHERE candidate.address = payload.address)
                                    AND NOT EXISTS (SELECT 1 FROM lease WHERE lease.address = payload.address)
                                    RETURNING address""")
            return set(item[0] for item in removed)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, body, media, address=None):
        self.connection.settimeout(2)
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(len(body)))
        if address:
            self.send_header("ETag", '"' + address + '"')
        self.end_headers()
        self.wfile.write(body)

    def dispatch(self, method):
        try:
            token = self.headers.get("Authorization", "")
            audience = self.server.sessions.get(token)
            if audience is None:
                raise Refusal(403, "not-authorized")
            fields = self.path.split("/")
            if method == "POST" and len(fields) == 5 and fields[:3] == ["", "v1", "lease"]:
                reply = self.server.store.issue(fields[3], fields[4], audience)
                self.send(201, json.dumps(reply, sort_keys=True).encode(), "application/json")
                return
            if method == "GET" and len(fields) == 4 and fields[:3] == ["", "v1", "payload"]:
                handle = fields[3]
                captured = self.server.store.preflight(handle, audience)
                self.server.pause(handle)
                self.server.store.deliver(handle, audience, captured, self.send)
                return
            raise Refusal(404, "unknown-operation")
        except Refusal as denied:
            self.send(denied.status, json.dumps({"code": denied.reason}).encode(), "application/json")

    def do_POST(self):
        self.dispatch("POST")

    def do_GET(self):
        self.dispatch("GET")


@contextmanager
def start(store, sessions, pause=lambda _: None):
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server.store = store
        server.sessions = sessions
        server.pause = pause
        serving = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        serving.start()
        try:
            yield server.server_address
        finally:
            server.shutdown()
            serving.join(timeout=2)
