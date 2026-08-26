from pathlib import Path

import aiosqlite
import bcrypt

from config import BANKING_DB_PATH

DB_PATH = str(BANKING_DB_PATH.resolve())


async def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            pin_hash TEXT NOT NULL,
            failed_pin_attempts INTEGER DEFAULT 0,
            is_locked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            account_type TEXT DEFAULT 'SAVINGS',
            balance REAL NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'INR',
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            source_account TEXT NOT NULL,
            destination_account TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            status TEXT NOT NULL,
            created_by TEXT NOT NULL,
            idempotency_key TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_account) REFERENCES accounts(account_id),
            FOREIGN KEY (destination_account) REFERENCES accounts(account_id),
            FOREIGN KEY (created_by) REFERENCES users(user_id)
        )
        """)
        await db.commit()


async def seed_data():
    async with aiosqlite.connect(DB_PATH) as db:
        pin_hash = bcrypt.hashpw("1234".encode(), bcrypt.gensalt()).decode()
        await db.execute(
            """
            INSERT OR IGNORE INTO users (user_id, name, email, pin_hash)
            VALUES (?, ?, ?, ?)
            """,
            ("USER001", "John Doe", "john@example.com", pin_hash),
        )

        pin2_hash = bcrypt.hashpw("5678".encode(), bcrypt.gensalt()).decode()
        await db.execute(
            """
            INSERT OR IGNORE INTO users (user_id, name, email, pin_hash)
            VALUES (?, ?, ?, ?)
            """,
            ("USER002", "David", "david@example.com", pin2_hash),
        )

        await db.execute(
            """
            INSERT OR IGNORE INTO accounts
                (account_id, user_id, account_type, balance)
            VALUES (?, ?, ?, ?)
            """,
            ("ACC001", "USER001", "SAVINGS", 100000),
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO accounts
                (account_id, user_id, account_type, balance)
            VALUES (?, ?, ?, ?)
            """,
            ("ACC002", "USER002", "SAVINGS", 50000),
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO transactions (
                transaction_id, source_account, destination_account,
                amount, currency, status, created_by, idempotency_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TXN1001",
                "ACC001",
                "ACC002",
                5000,
                "INR",
                "SUCCESS",
                "USER001",
                "MOCK-001",
            ),
        )
        await db.commit()


async def ensure_db():
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'users'
            """
        )
        if not await cursor.fetchone():
            raise RuntimeError(f"Failed to create tables in {DB_PATH}")
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        count = (await cursor.fetchone())[0]
    if count == 0:
        await seed_data()
