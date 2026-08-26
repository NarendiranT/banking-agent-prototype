"""FastMCP tool server for banking operations."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.database_db import ensure_db
from backend.service import (
    create_mock_transaction,
    get_account as lookup_account,
    get_transaction_status as lookup_transaction,
    get_user_account_by_pin as lookup_account_by_pin,
    transfer_money,
)


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    await ensure_db()
    await create_mock_transaction()
    try:
        yield {}
    finally:
        pass


mcp = FastMCP(
    "Banking MCP Server",
    instructions=(
        "Tools for transaction status, account balance, PIN identity, "
        "account validation, and transfers."
    ),
    lifespan=server_lifespan,
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mcp"})


@mcp.tool
async def get_transaction_status(transaction_id: str) -> dict:
    """Look up a transaction by ID."""
    transaction = await lookup_transaction(transaction_id)
    if not transaction:
        raise ToolError(f"Transaction {transaction_id} was not found.")
    return transaction


@mcp.tool
async def get_account_balance(account_id: str) -> dict:
    """Look up an account balance by account ID."""
    account = await lookup_account(account_id)
    if not account:
        raise ToolError(f"Account {account_id} was not found.")
    return account


@mcp.tool
async def validate_account(account_id: str) -> dict:
    """Validate that a destination account exists and is active."""
    account = await lookup_account(account_id)
    if not account:
        raise ToolError(f"Account {account_id} was not found.")
    return account


@mcp.tool
async def get_account_by_pin(
    pin: str,
    account_id: str | None = None,
) -> dict:
    """Identify a user and source account from a PIN and account ID."""
    result = await lookup_account_by_pin(pin, account_id)
    if not result:
        raise ToolError("Invalid PIN.")
    if result.get("is_locked"):
        raise ToolError("Account is locked.")
    if not result.get("account_id"):
        raise ToolError("No active account found for this user.")
    return result


@mcp.tool
async def execute_transaction(
    transaction_id: str,
    source_account: str,
    destination_account: str,
    amount: float,
    user_id: str = "USER001",
) -> dict:
    """Move funds between two accounts."""
    result = await transfer_money(
        transaction_id=transaction_id,
        source_account=source_account,
        destination_account=destination_account,
        amount=amount,
        user_id=user_id,
    )
    if not result.get("success"):
        raise ToolError(result.get("message", "Transaction failed."))
    return result


def run() -> None:
    mcp.run(transport="http", host="0.0.0.0", port=8001)


if __name__ == "__main__":
    run()
