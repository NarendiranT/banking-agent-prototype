"""HTTP MCP tool server for banking operations."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.database_db import init_db, seed_data
from backend.service import (
    create_mock_transaction,
    get_account,
    get_transaction_status,
    transfer_money,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_data()
    await create_mock_transaction()
    yield


app = FastAPI(
    title="Banking MCP Server",
    version="1.0.0",
    description="Prototype MCP tool server for transaction status, account validation, and transfers.",
    lifespan=lifespan,
)


class TransactionStatusRequest(BaseModel):
    transaction_id: str = Field(min_length=1)


class ValidateAccountRequest(BaseModel):
    account_id: str = Field(min_length=1)


class ExecuteTransactionRequest(BaseModel):
    transaction_id: str = Field(min_length=1)
    source_account: str = Field(min_length=1)
    destination_account: str = Field(min_length=1)
    amount: float = Field(gt=0)
    user_id: str = Field(default="USER001")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp"}


@app.get("/tools")
async def list_tools():
    return {
        "tools": [
            {
                "name": "get_transaction_status",
                "description": "Look up a transaction by ID.",
                "path": "/tools/get_transaction_status",
            },
            {
                "name": "validate_account",
                "description": "Validate that a destination account exists and is active.",
                "path": "/tools/validate_account",
            },
            {
                "name": "execute_transaction",
                "description": "Move funds between two accounts.",
                "path": "/tools/execute_transaction",
            },
        ]
    }


@app.post("/tools/get_transaction_status")
async def get_transaction_status_tool(request: TransactionStatusRequest):
    transaction = await get_transaction_status(request.transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction {request.transaction_id} was not found.",
        )
    return transaction


@app.post("/tools/validate_account")
async def validate_account_tool(request: ValidateAccountRequest):
    account = await get_account(request.account_id)
    if not account:
        raise HTTPException(
            status_code=404,
            detail=f"Account {request.account_id} was not found.",
        )
    return account


@app.post("/tools/execute_transaction")
async def execute_transaction_tool(request: ExecuteTransactionRequest):
    result = await transfer_money(
        transaction_id=request.transaction_id,
        source_account=request.source_account,
        destination_account=request.destination_account,
        amount=request.amount,
        user_id=request.user_id,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("message", "Transaction failed."),
        )
    return result


def run():
    import uvicorn

    uvicorn.run(
        "mcp.server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )


if __name__ == "__main__":
    run()
