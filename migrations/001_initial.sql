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
