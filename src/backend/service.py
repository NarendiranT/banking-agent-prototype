import bcrypt
import aiosqlite

from database_db import DB_PATH


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