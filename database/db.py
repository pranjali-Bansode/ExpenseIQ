import os
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "expenseiq.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            phone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Budget Table
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            month TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, category, month)
        );

        -- Recurring Expenses Table
        CREATE TABLE IF NOT EXISTS recurring_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            frequency TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            next_due_date TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS recurring_expense_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recurring_expense_id INTEGER NOT NULL REFERENCES recurring_expenses(id),
            expense_id INTEGER NOT NULL REFERENCES expenses(id),
            generated_date TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # ---- MIGRATION: add `phone` column for existing DBs created before
    # this column existed. CREATE TABLE IF NOT EXISTS above only helps on
    # a brand-new database, so older sqlite files need an explicit ALTER. ----
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "phone" not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        conn.commit()

    conn.close()


def create_user(name, email, password, phone=None):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash, phone) VALUES (?, ?, ?, ?)",
        (name, email, generate_password_hash(password), phone or None),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def update_user_phone(user_id, phone):
    conn = get_db()
    conn.execute(
        "UPDATE users SET phone = ? WHERE id = ?",
        (phone or None, user_id),
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return user


def seed_db():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()

    if row[0] > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@expenseiq.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    expenses = [
        (user_id, 450.00, "Food", "2026-04-01", "Groceries from D-Mart"),
        (user_id, 120.00, "Transport", "2026-04-02", "Metro recharge"),
        (user_id, 1200.00, "Bills", "2026-04-03", "Electricity bill"),
        (user_id, 350.00, "Health", "2026-04-05", "Pharmacy"),
        (user_id, 500.00, "Entertainment", "2026-04-06", "Movie"),
        (user_id, 800.00, "Shopping", "2026-04-07", "Earphones"),
        (user_id, 200.00, "Other", "2026-04-08", "Misc"),
        (user_id, 180.00, "Food", "2026-04-08", "Lunch"),
    ]

    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )

    conn.commit()
    conn.close()