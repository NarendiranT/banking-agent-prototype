
import asyncio
from collections import defaultdict
from typing import Any
from contextlib import asynccontextmanager


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langgraph.types import Command

from database_db import init_db, seed_data
from graph.app import graph
from service import verify_pin

@asynccontextmanager
async def lifespan(app: FastAPI):

    await init_db()
    await seed_data()

    yield


app = FastAPI(
    title="Banking Agent API",
    lifespan=lifespan,
    version="1.0.0",
    description="Agentic banking prototype using LangGraph, MCP and HITL approval.",
)

thread_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


class ChatRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    user_id: str = Field(default="USER001")
    message: str = Field(min_length=1)


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    pin: str = Field(min_length=4, max_length=6)


class RejectRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)


def get_config(thread_id: str) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": thread_id
        }
    }


def get_interrupt_payload(state) -> dict | None:
    pending_transaction = state.values.get(
        "pending_transaction"
    )

    if not pending_transaction:
        return None

    return pending_transaction


@app.post("/chat")
async def chat(request: ChatRequest):

    lock = thread_locks[request.thread_id]

    async with lock:

        config = get_config(
            request.thread_id
        )

        input_state = {
            "user_id": request.user_id,

            "messages": [
                {
                    "role": "user",
                    "content": request.message
                }
            ]
        }

        try:

            result = await graph.ainvoke(
                input_state,
                config=config
            )


            graph_state = await graph.aget_state(
                config
            )

            if graph_state.next:

                pending_transaction = (
                    get_interrupt_payload(
                        graph_state
                    )
                )

                if pending_transaction:

                    return {
                        "status": "approval_required",

                        "message": (
                            "Please review the transaction "
                            "and enter your PIN to approve."
                        ),

                        "transaction": (
                            pending_transaction
                        )
                    }


            return {
                "status": "completed",

                "message": result.get(
                    "answer",
                    "Request completed."
                )
            }

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail=f"Graph execution failed: {exc}"
            )


@app.post("/approve")
async def approve_transaction(
    request: ApprovalRequest
):

    lock = thread_locks[
        request.thread_id
    ]

    async with lock:

        config = get_config(
            request.thread_id
        )

        try:


            graph_state = await graph.aget_state(
                config
            )

            pending_transaction = (
                graph_state.values.get(
                    "pending_transaction"
                )
            )

            if not pending_transaction:

                raise HTTPException(
                    status_code=404,
                    detail=(
                        "No pending transaction found "
                        "for this conversation."
                    )
                )

            stored_transaction_id = (
                pending_transaction.get(
                    "transaction_id"
                )
            )

            if (
                stored_transaction_id
                != request.transaction_id
            ):

                raise HTTPException(
                    status_code=400,
                    detail="Transaction ID mismatch."
                )


            user_id = graph_state.values.get(
                "user_id"
            )

            if not user_id:

                raise HTTPException(
                    status_code=400,
                    detail="User information unavailable."
                )

            pin_valid = await verify_pin(
                user_id=user_id,
                pin=request.pin
            )

            if not pin_valid:

                raise HTTPException(
                    status_code=401,
                    detail="Invalid transaction PIN."
                )


            result = await graph.ainvoke(

                Command(
                    resume={
                        "approved": True,
                        "auth_verified": True,
                        "transaction_id":
                            request.transaction_id
                    }
                ),

                config=config
            )

            new_state = await graph.aget_state(
                config
            )

            if new_state.next:

                return {
                    "status": "processing",
                    "message": (
                        "Transaction is still being "
                        "processed."
                    )
                }


            return {
                "status": "completed",

                "message": result.get(
                    "answer",
                    (
                        "Transaction completed "
                        "successfully."
                    )
                ),

                "transaction": result.get(
                    "transaction_result"
                )
            }

        except HTTPException:
            raise

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Transaction approval failed: {exc}"
                )
            )


@app.post("/reject")
async def reject_transaction(
    request: RejectRequest
):

    lock = thread_locks[
        request.thread_id
    ]

    async with lock:

        config = get_config(
            request.thread_id
        )

        try:

            graph_state = await graph.aget_state(
                config
            )

            pending_transaction = (
                graph_state.values.get(
                    "pending_transaction"
                )
            )

            if not pending_transaction:

                raise HTTPException(
                    status_code=404,
                    detail="No pending transaction found."
                )

            stored_transaction_id = (
                pending_transaction.get(
                    "transaction_id"
                )
            )

            if (
                stored_transaction_id
                != request.transaction_id
            ):

                raise HTTPException(
                    status_code=400,
                    detail="Transaction ID mismatch."
                )


            result = await graph.ainvoke(

                Command(
                    resume={
                        "approved": False,
                        "auth_verified": False,
                        "transaction_id":
                            request.transaction_id
                    }
                ),

                config=config
            )

            return {
                "status": "cancelled",

                "message": result.get(
                    "answer",
                    "Transaction cancelled."
                )
            }

        except HTTPException:
            raise

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail=f"Transaction rejection failed: {exc}"
            )


@app.get("/threads/{thread_id}")
async def get_thread_state(
    thread_id: str
):

    lock = thread_locks[
        thread_id
    ]

    async with lock:

        config = get_config(
            thread_id
        )

        try:

            state = await graph.aget_state(
                config
            )

            if not state.values:

                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found."
                )

            # Be careful not to expose sensitive information.
            return {
                "thread_id": thread_id,

                "user_id": state.values.get(
                    "user_id"
                ),

                "approval_status":
                    state.values.get(
                        "approval_status"
                    ),

                "pending_transaction":
                    state.values.get(
                        "pending_transaction"
                    ),

                "next_nodes": list(
                    state.next
                )
            }

        except HTTPException:
            raise

        except Exception as exc:

            raise HTTPException(
                status_code=500,
                detail=f"Unable to read thread: {exc}"
            )


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )