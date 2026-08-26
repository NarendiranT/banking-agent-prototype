import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, Field

from backend.database_db import init_db, seed_data
from backend.service import create_mock_transaction, verify_pin
from graph.app import close_graph, get_graph, init_runtime_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_data()
    await create_mock_transaction()
    await init_runtime_graph()
    yield
    await close_graph()


app = FastAPI(
    title="Banking Agent API",
    lifespan=lifespan,
    version="1.0.0",
    description=(
        "Agentic banking prototype using LangGraph, MCP and HITL approval."
    ),
)

thread_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api"}


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    user_id: str | None = None
    message: str = Field(min_length=1)


class IdentifyRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    pin: str = Field(min_length=4, max_length=6)
    account_id: str = Field(min_length=1)


class StatusLookupRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    pin: str = Field(min_length=4, max_length=6)


class RejectRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)


def get_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def get_graph_interrupt(state) -> dict | None:
    interrupts = getattr(state, "interrupts", None) or ()
    for item in interrupts:
        value = getattr(item, "value", item)
        if isinstance(value, dict):
            return value

    for task in getattr(state, "tasks", None) or ():
        for item in getattr(task, "interrupts", None) or ():
            value = getattr(item, "value", item)
            if isinstance(value, dict):
                return value

    pending_transaction = state.values.get("pending_transaction")
    if pending_transaction and state.next:
        return {
            "type": "transaction_approval",
            "transaction": pending_transaction,
        }

    next_nodes = list(state.next or ())
    if "transaction_status" in next_nodes:
        return {
            "type": "transaction_status",
            "transaction_id": state.values.get("transaction_id"),
            "source_account": state.values.get("source_account"),
        }
    if "set_user_account" in next_nodes:
        return {
            "type": "set_user_account",
            "message": (
                "Enter your PIN and account ID to identify your account."
            ),
        }
    return None


def interrupt_http_response(state) -> dict | None:
    if not state.next:
        return None

    payload = get_graph_interrupt(state)
    if not payload:
        return None

    if payload.get("type") == "set_user_account":
        return {
            "status": "pin_required",
            "message": payload.get(
                "message",
                "Enter your PIN and account ID to identify your account.",
            ),
        }

    if payload.get("type") == "transaction_status":
        return {
            "status": "txn_id_required",
            "message": payload.get(
                "message",
                "Enter the transaction ID to look up.",
            ),
            "transaction_id": payload.get("transaction_id"),
            "source_account": payload.get("source_account"),
        }

    transaction = payload.get("transaction") or state.values.get(
        "pending_transaction"
    )
    if transaction:
        return {
            "status": "approval_required",
            "message": (
                "Please review the transaction "
                "and enter your PIN to approve."
            ),
            "transaction": transaction,
        }
    return None


@app.post("/chat")
async def chat(request: ChatRequest):
    lock = thread_locks[request.thread_id]
    async with lock:
        graph = get_graph()
        config = get_config(request.thread_id)
        input_state = {
            "messages": [{"role": "user", "content": request.message}],
        }
        if request.user_id:
            input_state["user_id"] = request.user_id

        try:
            result = await graph.ainvoke(input_state, config=config)
            graph_state = await graph.aget_state(config)
            paused = interrupt_http_response(graph_state)
            if paused:
                return paused
            return {
                "status": "completed",
                "message": result.get("answer", "Request completed."),
            }
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Graph execution failed: {exc}",
            )


@app.post("/identify")
async def identify_account(request: IdentifyRequest):
    lock = thread_locks[request.thread_id]
    async with lock:
        graph = get_graph()
        config = get_config(request.thread_id)
        try:
            graph_state = await graph.aget_state(config)
            if "set_user_account" not in graph_state.next:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No account identification is pending "
                        "for this conversation."
                    ),
                )

            result = await graph.ainvoke(
                Command(resume={
                    "pin": request.pin,
                    "account_id": request.account_id.strip().upper(),
                }),
                config=config,
            )
            graph_state = await graph.aget_state(config)
            paused = interrupt_http_response(graph_state)
            if paused:
                return paused
            return {
                "status": "completed",
                "message": result.get("answer", "Account identified."),
                "user_id": graph_state.values.get("user_id"),
                "source_account": graph_state.values.get("source_account"),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Account identification failed: {exc}",
            )


@app.post("/lookup")
async def lookup_transaction_status(request: StatusLookupRequest):
    lock = thread_locks[request.thread_id]
    async with lock:
        graph = get_graph()
        config = get_config(request.thread_id)
        try:
            graph_state = await graph.aget_state(config)
            if "transaction_status" not in graph_state.next:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No transaction status lookup is pending "
                        "for this conversation."
                    ),
                )

            result = await graph.ainvoke(
                Command(resume={
                    "transaction_id": request.transaction_id.strip().upper(),
                }),
                config=config,
            )
            graph_state = await graph.aget_state(config)
            paused = interrupt_http_response(graph_state)
            if paused:
                return paused
            return {
                "status": "completed",
                "message": result.get(
                    "answer",
                    "Transaction status lookup completed.",
                ),
                "transaction": result.get("transaction_result"),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Transaction status lookup failed: {exc}",
            )


@app.post("/approve")
async def approve_transaction(request: ApprovalRequest):
    lock = thread_locks[request.thread_id]
    async with lock:
        graph = get_graph()
        config = get_config(request.thread_id)
        try:
            graph_state = await graph.aget_state(config)
            pending_transaction = graph_state.values.get(
                "pending_transaction"
            )
            if not pending_transaction:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "No pending transaction found for this conversation."
                    ),
                )

            stored_transaction_id = pending_transaction.get("transaction_id")
            if stored_transaction_id != request.transaction_id:
                raise HTTPException(
                    status_code=400,
                    detail="Transaction ID mismatch.",
                )

            user_id = graph_state.values.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=400,
                    detail="User information unavailable.",
                )

            pin_valid = await verify_pin(user_id=user_id, pin=request.pin)
            if not pin_valid:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid transaction PIN.",
                )

            result = await graph.ainvoke(
                Command(resume={
                    "approved": True,
                    "auth_verified": True,
                    "transaction_id": request.transaction_id,
                }),
                config=config,
            )
            new_state = await graph.aget_state(config)
            if new_state.next:
                return {
                    "status": "processing",
                    "message": "Transaction is still being processed.",
                }
            return {
                "status": "completed",
                "message": result.get(
                    "answer",
                    "Transaction completed successfully.",
                ),
                "transaction": result.get("transaction_result"),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Transaction approval failed: {exc}",
            )


@app.post("/reject")
async def reject_transaction(request: RejectRequest):
    lock = thread_locks[request.thread_id]
    async with lock:
        graph = get_graph()
        config = get_config(request.thread_id)
        try:
            graph_state = await graph.aget_state(config)
            pending_transaction = graph_state.values.get(
                "pending_transaction"
            )
            if not pending_transaction:
                raise HTTPException(
                    status_code=404,
                    detail="No pending transaction found.",
                )

            stored_transaction_id = pending_transaction.get("transaction_id")
            if stored_transaction_id != request.transaction_id:
                raise HTTPException(
                    status_code=400,
                    detail="Transaction ID mismatch.",
                )

            result = await graph.ainvoke(
                Command(resume={
                    "approved": False,
                    "auth_verified": False,
                    "transaction_id": request.transaction_id,
                }),
                config=config,
            )
            return {
                "status": "cancelled",
                "message": result.get("answer", "Transaction cancelled."),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Transaction rejection failed: {exc}",
            )


@app.get("/threads/{thread_id}")
async def get_thread_state(thread_id: str):
    lock = thread_locks[thread_id]
    async with lock:
        graph = get_graph()
        config = get_config(thread_id)
        try:
            state = await graph.aget_state(config)
            if not state.values:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found.",
                )
            # Be careful not to expose sensitive information.
            return {
                "thread_id": thread_id,
                "user_id": state.values.get("user_id"),
                "source_account": state.values.get("source_account"),
                "approval_status": state.values.get("approval_status"),
                "pending_transaction": state.values.get(
                    "pending_transaction"
                ),
                "next_nodes": list(state.next),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Unable to read thread: {exc}",
            )


def run():
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    run()
