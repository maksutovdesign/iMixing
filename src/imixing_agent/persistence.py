from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE,
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  title TEXT,
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
CREATE INDEX IF NOT EXISTS idx_waitlist_email ON waitlist_signups(email);
"""


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
                (id, genre, target, status, input_dir, output_dir, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, genre, target, status, str(input_dir), str(output_dir), created_at, updated_at),
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
