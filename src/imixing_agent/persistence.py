from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE,
  display_name TEXT,
  password_hash TEXT,
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  expires_at REAL NOT NULL,
  created_at REAL NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  title TEXT,
  kind TEXT NOT NULL DEFAULT 'workspace',
  status TEXT NOT NULL DEFAULT 'ready',
  metadata_json TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audio_jobs (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  genre TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  input_dir TEXT NOT NULL,
  output_dir TEXT NOT NULL,
  error TEXT,
  warnings_json TEXT,
  result_json TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS credit_sessions (
  id TEXT PRIMARY KEY,
  balance INTEGER NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS credits_ledger (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  delta INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  reason TEXT NOT NULL,
  feature TEXT,
  created_at REAL NOT NULL,
  FOREIGN KEY(session_id) REFERENCES credit_sessions(id)
);

CREATE TABLE IF NOT EXISTS waitlist_signups (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  name TEXT,
  role TEXT,
  message TEXT,
  source TEXT,
  created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audio_jobs_status ON audio_jobs(status);
CREATE INDEX IF NOT EXISTS idx_projects_user_updated ON projects(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_waitlist_email ON waitlist_signups(email);
"""


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    display_name: str | None


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    title: str
    kind: str
    status: str
    metadata_json: str | None
    created_at: float
    updated_at: float


class AppDatabase:
    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// URLs are supported by the MVP persistence adapter.")
        self.path = Path(database_url.removeprefix("sqlite:///")).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._add_column_if_missing(connection, "users", "display_name", "TEXT")
            self._add_column_if_missing(connection, "users", "password_hash", "TEXT")
            self._add_column_if_missing(connection, "projects", "kind", "TEXT NOT NULL DEFAULT 'workspace'")
            self._add_column_if_missing(connection, "projects", "status", "TEXT NOT NULL DEFAULT 'ready'")
            self._add_column_if_missing(connection, "projects", "metadata_json", "TEXT")

    @staticmethod
    def _add_column_if_missing(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_account(self, *, email: str, password_hash: str, display_name: str | None = None) -> Account:
        now = time.time()
        account = Account(id=uuid.uuid4().hex, email=email, display_name=display_name)
        try:
            with self.connect() as connection:
                connection.execute(
                    "INSERT INTO users (id, email, display_name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                    (account.id, account.email, account.display_name, password_hash, now),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("An account with this email already exists.") from error
        return account

    def account_by_email(self, email: str) -> tuple[Account, str] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, email, display_name, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
        if row is None or not row["password_hash"]:
            return None
        return Account(id=row["id"], email=row["email"], display_name=row["display_name"]), str(row["password_hash"])

    def create_auth_session(self, user_id: str, *, lifetime_seconds: int) -> str:
        now = time.time()
        session_id = uuid.uuid4().hex
        with self.connect() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now,))
            connection.execute(
                "INSERT INTO auth_sessions (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (session_id, user_id, now + lifetime_seconds, now),
            )
        return session_id

    def account_for_session(self, session_id: str | None) -> Account | None:
        if not session_id:
            return None
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.email, users.display_name
                FROM auth_sessions JOIN users ON users.id = auth_sessions.user_id
                WHERE auth_sessions.id = ? AND auth_sessions.expires_at > ?
                """,
                (session_id, time.time()),
            ).fetchone()
        if row is None:
            return None
        return Account(id=row["id"], email=row["email"], display_name=row["display_name"])

    def revoke_auth_session(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self.connect() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE id = ?", (session_id,))

    def create_project(
        self,
        *,
        user_id: str,
        title: str,
        kind: str,
        status: str = "ready",
        metadata_json: str | None = None,
    ) -> ProjectRecord:
        now = time.time()
        project = ProjectRecord(
            id=uuid.uuid4().hex,
            title=title[:160] or "Untitled project",
            kind=kind[:40] or "workspace",
            status=status[:40] or "ready",
            metadata_json=metadata_json,
            created_at=now,
            updated_at=now,
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (id, user_id, title, kind, status, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project.id, user_id, project.title, project.kind, project.status, project.metadata_json, now, now),
            )
        return project

    def list_projects(self, user_id: str, *, limit: int = 40) -> list[ProjectRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, kind, status, metadata_json, created_at, updated_at
                FROM projects WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?
                """,
                (user_id, max(1, min(limit, 100))),
            ).fetchall()
        return [ProjectRecord(**dict(row)) for row in rows]

    def update_project_status(self, project_id: str, *, status: str, metadata_json: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE projects SET status = ?, metadata_json = COALESCE(?, metadata_json), updated_at = ?
                WHERE id = ?
                """,
                (status[:40], metadata_json, time.time(), project_id),
            )

    def ensure_credit_session(self, session_id: str | None, default_balance: int) -> str:
        now = time.time()
        resolved = session_id or uuid.uuid4().hex
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM credit_sessions WHERE id = ?", (resolved,)).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO credit_sessions (id, balance, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (resolved, default_balance, now, now),
                )
                connection.execute(
                    "INSERT INTO credits_ledger (id, session_id, delta, balance_after, reason, feature, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (uuid.uuid4().hex, resolved, default_balance, default_balance, "initial_demo_balance", None, now),
                )
        return resolved

    def credit_balance(self, session_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT balance FROM credit_sessions WHERE id = ?", (session_id,)).fetchone()
        return int(row["balance"]) if row else 0

    def set_credit_balance(self, session_id: str, balance: int, *, reason: str, feature: str | None = None) -> int:
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                "UPDATE credit_sessions SET balance = ?, updated_at = ? WHERE id = ?",
                (balance, now, session_id),
            )
            connection.execute(
                "INSERT INTO credits_ledger (id, session_id, delta, balance_after, reason, feature, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, session_id, 0, balance, reason, feature, now),
            )
        return balance

    def change_credits(self, session_id: str, delta: int, *, reason: str, feature: str | None = None) -> int:
        now = time.time()
        with self.connect() as connection:
            row = connection.execute("SELECT balance FROM credit_sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                raise KeyError(session_id)
            balance = int(row["balance"]) + delta
            connection.execute(
                "UPDATE credit_sessions SET balance = ?, updated_at = ? WHERE id = ?",
                (balance, now, session_id),
            )
            connection.execute(
                "INSERT INTO credits_ledger (id, session_id, delta, balance_after, reason, feature, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, session_id, delta, balance, reason, feature, now),
            )
        return balance

    def save_audio_job(
        self,
        *,
        job_id: str,
        project_id: str | None,
        genre: str,
        target: str,
        status: str,
        input_dir: Path,
        output_dir: Path,
        created_at: float,
        updated_at: float,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO audio_jobs
                (id, project_id, genre, target, status, input_dir, output_dir, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, project_id, genre, target, status, str(input_dir), str(output_dir), created_at, updated_at),
            )

    def update_audio_job(
        self,
        job_id: str,
        *,
        status: str,
        updated_at: float,
        error: str | None = None,
        warnings_json: str | None = None,
        result_json: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE audio_jobs
                SET status = ?, updated_at = ?, error = COALESCE(?, error),
                    warnings_json = COALESCE(?, warnings_json),
                    result_json = COALESCE(?, result_json)
                WHERE id = ?
                """,
                (status, updated_at, error, warnings_json, result_json, job_id),
            )

    def add_waitlist_signup(
        self,
        *,
        email: str,
        name: str | None,
        role: str | None,
        message: str | None,
        source: str | None,
    ) -> str:
        signup_id = uuid.uuid4().hex
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO waitlist_signups (id, email, name, role, message, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (signup_id, email, name, role, message, source, time.time()),
            )
        return signup_id
