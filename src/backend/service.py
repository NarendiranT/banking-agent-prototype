import uuid

import aiosqlite
import bcrypt

from backend.database_db import DB_PATH


async def get_user_account_by_pin(
    pin: str,
    account_id: str | None = None,
) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                user_id,
                name,
                pin_hash,
                is_locked
            FROM users
            """
        )
        users = await cursor.fetchall()

        matched = None
        for user in users:
            if bcrypt.checkpw(pin.encode(), user["pin_hash"].encode()):
                matched = user
                break

        if not matched:
            return None

        if matched["is_locked"]:
            return {
                "user_id": matched["user_id"],
                "name": matched["name"],
                "is_locked": True,
            }

        if account_id:
            cursor = await db.execute(
                """
                SELECT
                    account_id,
                    user_id,
                    account_type,
                    balance,
                    currency,
                    status
                FROM accounts
                WHERE user_id = ?
                  AND account_id = ?
                  AND status = 'ACTIVE'
                """,
                (matched["user_id"], account_id.upper()),
            )
        else:
            cursor = await db.execute(
                """
                SELECT
                    account_id,
                    user_id,
                    account_type,
                    balance,
                    currency,
                    status
                FROM accounts
                WHERE user_id = ?
                  AND status = 'ACTIVE'
                ORDER BY created_at
                LIMIT 1
                """,
                (matched["user_id"],),
            )
        account = await cursor.fetchone()

        if not account:
            return {
                "user_id": matched["user_id"],
                "name": matched["name"],
                "is_locked": False,
            }

        return {
            **dict(account),
            "name": matched["name"],
            "is_locked": False,
        }


async def verify_pin(
    user_id: str,
    pin: str
) -> bool:

    async with aiosqlite.connect(DB_PATH) as db:

        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                pin_hash,
                failed_pin_attempts,
                is_locked
            FROM users
            WHERE user_id = ?
            """,
            (user_id,)
        )

        user = await cursor.fetchone()

        if not user:
            return False

        if user["is_locked"]:
            return False

        valid = bcrypt.checkpw(
            pin.encode(),
            user["pin_hash"].encode()
        )

        if valid:

            await db.execute(
                """
                UPDATE users
                SET failed_pin_attempts = 0
                WHERE user_id = ?
                """,
                (user_id,)
            )

            await db.commit()

            return True

        failed_attempts = (
            user["failed_pin_attempts"] + 1
        )

        if failed_attempts >= 3:

            await db.execute(
                """
                UPDATE users
                SET
                    failed_pin_attempts = ?,
                    is_locked = 1
                WHERE user_id = ?
                """,
                (
                    failed_attempts,
                    user_id
                )
            )

        else:

            await db.execute(
                """
                UPDATE users
                SET failed_pin_attempts = ?
                WHERE user_id = ?
                """,
                (
                    failed_attempts,
                    user_id
                )
            )

        await db.commit()

        return False


async def get_transaction_status(
    transaction_id: str
):

    async with aiosqlite.connect(DB_PATH) as db:

        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                transaction_id,
                source_account,
                destination_account,
                amount,
                currency,
                status,
                created_at
            FROM transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,)
        )

        transaction = await cursor.fetchone()

        if not transaction:
            return None

        return dict(transaction)


async def get_account(account_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                account_id,
                user_id,
                account_type,
                balance,
                currency,
                status
            FROM accounts
            WHERE account_id = ?
            """,
            (account_id,),
        )

        account = await cursor.fetchone()

        if not account:
            return None

        return dict(account)


async def create_mock_transaction():

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            INSERT OR IGNORE INTO transactions
            (
                transaction_id,
                source_account,
                destination_account,
                amount,
                currency,
                status,
                created_by,
                idempotency_key
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
                "MOCK-001"
            )
        )

        await db.commit()


async def transfer_money(
    transaction_id: str,
    source_account: str,
    destination_account: str,
    amount: float,
    user_id: str,
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")

        try:
            existing_cursor = await db.execute(
                """
                SELECT *
                FROM transactions
                WHERE transaction_id = ?
                   OR idempotency_key = ?
                """,
                (transaction_id, transaction_id),
            )
            existing = await existing_cursor.fetchone()

            if existing:
                await db.commit()
                return {
                    **dict(existing),
                    "success": existing["status"] == "SUCCESS",
                    "message": "Transaction already processed.",
                }

            source_cursor = await db.execute(
                """
                SELECT *
                FROM accounts
                WHERE account_id = ?
                """,
                (source_account,),
            )
            source = await source_cursor.fetchone()

            destination_cursor = await db.execute(
                """
                SELECT *
                FROM accounts
                WHERE account_id = ?
                """,
                (destination_account,),
            )
            destination = await destination_cursor.fetchone()

            if not source or not destination:
                await db.rollback()
                return {
                    "success": False,
                    "message": "Source or destination account was not found.",
                }

            if source["status"] != "ACTIVE" or destination["status"] != "ACTIVE":
                await db.rollback()
                return {
                    "success": False,
                    "message": "Source or destination account is not active.",
                }

            if source["balance"] < amount:
                await db.rollback()
                return {
                    "success": False,
                    "message": "Insufficient balance.",
                }

            await db.execute(
                """
                UPDATE accounts
                SET balance = balance - ?
                WHERE account_id = ?
                """,
                (amount, source_account),
            )
            await db.execute(
                """
                UPDATE accounts
                SET balance = balance + ?
                WHERE account_id = ?
                """,
                (amount, destination_account),
            )

            final_transaction_id = "TXN" + uuid.uuid4().hex[:8].upper()

            await db.execute(
                """
                INSERT INTO transactions
                (
                    transaction_id,
                    source_account,
                    destination_account,
                    amount,
                    currency,
                    status,
                    created_by,
                    idempotency_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    final_transaction_id,
                    source_account,
                    destination_account,
                    amount,
                    "INR",
                    "SUCCESS",
                    user_id,
                    transaction_id,
                ),
            )

            await db.commit()

            return {
                "success": True,
                "transaction_id": final_transaction_id,
                "source_account": source_account,
                "destination_account": destination_account,
                "amount": amount,
                "status": "SUCCESS",
            }

        except Exception as exc:
            await db.rollback()
            return {
                "success": False,
                "message": f"Transaction failed: {exc}",
            }