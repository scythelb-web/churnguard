import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "churnguard.db"

# Turso (libsql) support — persistent SQLite on the edge
# Set TURSO_DATABASE_URL + TURSO_AUTH_TOKEN to use Turso instead of local SQLite
TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

_use_turso = bool(TURSO_URL and TURSO_TOKEN)

if _use_turso:
    try:
        import libsql_experimental as libsql
        _turso_available = True
    except ImportError:
        _turso_available = False


def _connect():
    """Return a database connection — Turso if configured, else local SQLite."""
    if _use_turso and _turso_available:
        conn = libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                stripe_customer_id TEXT,
                plan TEXT DEFAULT 'starter',
                stripe_account_id TEXT,
                stripe_connect_active INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS customer_stripe_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                stripe_account_id TEXT UNIQUE NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS failed_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                stripe_customer_id TEXT NOT NULL,
                stripe_invoice_id TEXT NOT NULL,
                stripe_payment_intent_id TEXT,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'usd',
                decline_code TEXT,
                failure_message TEXT,
                attempt_count INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolved_status TEXT
            );

            CREATE TABLE IF NOT EXISTS dunning_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                failed_payment_id INTEGER NOT NULL REFERENCES failed_payments(id),
                step_number INTEGER NOT NULL,
                channel TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                opened INTEGER DEFAULT 0,
                clicked INTEGER DEFAULT 0,
                recovered INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS dunning_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                channel TEXT NOT NULL,
                subject TEXT,
                body_html TEXT NOT NULL,
                is_default INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS recovery_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                month TEXT NOT NULL,
                total_failed INTEGER DEFAULT 0,
                total_recovered INTEGER DEFAULT 0,
                total_amount_failed INTEGER DEFAULT 0,
                total_amount_recovered INTEGER DEFAULT 0,
                UNIQUE(user_id, month)
            );
        """)
