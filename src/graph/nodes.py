import re
import uuid

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from graph.state import AgentState
from mcp.mcp_client import (
    mcp_get_transaction_status,
    mcp_validate_account,
    mcp_execute_transaction,
)


async def conversation_agent(
    state: AgentState
) -> dict:

    message = state["messages"][-1].content

    text = message.lower()


    if (
        "status" in text
        or "transaction" in text
        and "check" in text
    ):

        match = re.search(
            r"(TXN[\w\d]+)",
            message,
            re.IGNORECASE
        )

        if match:

            return {
                "intent": "status",
                "transaction_id":
                    match.group(1).upper()
            }


    if (
        "transfer" in text
        or "send" in text
        or "pay" in text
    ):

        account_match = re.search(
            r"(ACC[\w\d]+)",
            message,
            re.IGNORECASE
        )

        amount_match = re.search(
            r"[\₹₹]?\s*([\d,]+(?:\.\d+)?)",
            message
        )

        if account_match and amount_match:

            amount = float(
                amount_match
                .group(1)
                .replace(",", "")
            )

            return {
                "intent": "transfer",

                # Prototype:
                # user's source account
                "source_account": "ACC001",

                "destination_account":
                    account_match.group(1).upper(),

                "amount": amount
            }

    return {
        "intent": "unknown"
    }


async def transaction_status(
    state: AgentState
) -> dict:

    transaction_id = state[
        "transaction_id"
    ]

    # MCP call
    transaction = (
        await mcp_get_transaction_status(
            transaction_id
        )
    )

    if not transaction:

        return {
            "answer": (
                f"I could not find transaction "
                f"{transaction_id}."
            )
        }

    return {
        "transaction_result": transaction,

        "answer": (
            f"Transaction "
            f"{transaction['transaction_id']} "
            f"for ₹{transaction['amount']:,.2f} "
            f"is currently "
            f"{transaction['status']}."
        )
    }

async def validate_transaction(
    state: AgentState
) -> dict:

    source = state[
        "source_account"
    ]

    destination = state[
        "destination_account"
    ]

    amount = state[
        "amount"
    ]

    if amount <= 0:

        return {
            "answer":
                "Transaction amount must be greater than zero.",

            "intent":
                "validation_failed"
        }

    if source == destination:

        return {
            "answer":
                "Source and destination accounts cannot be the same.",

            "intent":
                "validation_failed"
        }

    account = await mcp_validate_account(
        destination
    )

    if not account:

        return {
            "answer":
                f"Account {destination} was not found.",

            "intent":
                "validation_failed"
        }

    if account["status"] != "ACTIVE":

        return {
            "answer":
                "Destination account is not active.",

            "intent":
                "validation_failed"
        }

    return {}


async def risk_check(
    state: AgentState
) -> dict:

    amount = state["amount"]

    if amount > 50000:

        risk_level = "HIGH"

    elif amount > 10000:

        risk_level = "MEDIUM"

    else:

        risk_level = "LOW"

    transaction_id = (
        "PENDING_"
        + uuid.uuid4().hex[:8].upper()
    )

    pending_transaction = {

        "transaction_id":
            transaction_id,

        "source_account":
            state["source_account"],

        "destination_account":
            state["destination_account"],

        "amount":
            state["amount"],

        "risk_level":
            risk_level,

        "status":
            "PENDING_APPROVAL"
    }

    return {
        "risk_level": risk_level,

        "pending_transaction":
            pending_transaction
    }


async def approval_node(
    state: AgentState
) -> dict:

    pending = state[
        "pending_transaction"
    ]

    approval = interrupt(
        {
            "type":
                "transaction_approval",

            "transaction":
                pending
        }
    )

    if not approval.get(
        "approved",
        False
    ):

        return {
            "approval_status":
                "rejected",

            "auth_verified":
                False
        }

    return {
        "approval_status":
            "approved",

        "auth_verified":
            approval.get(
                "auth_verified",
                False
            )
    }


async def execute_transaction(
    state: AgentState
) -> dict:

    if not state.get(
        "auth_verified"
    ):

        return {
            "answer":
                "Transaction authentication failed."
        }

    pending = state[
        "pending_transaction"
    ]

    result = (
        await mcp_execute_transaction(
            transaction_id=
                pending["transaction_id"],

            source_account=
                pending["source_account"],

            destination_account=
                pending["destination_account"],

            amount=
                pending["amount"],

            user_id=
                state["user_id"]
        )
    )

    if not result.get(
        "success"
    ):

        return {
            "transaction_result":
                result,

            "answer":
                result.get(
                    "message",
                    "Transaction failed."
                )
        }

    return {
        "transaction_result":
            result,

        "pending_transaction":
            None,

        "answer": (
            f"Transaction completed successfully.\n\n"
            f"Transaction ID: "
            f"{result['transaction_id']}\n\n"
            f"Amount: "
            f"₹{result['amount']:,.2f}"
        )
    }


async def cancel_transaction(
    state: AgentState
) -> dict:

    pending = state.get(
        "pending_transaction"
    )

    transaction_id = None

    if pending:
        transaction_id = pending.get(
            "transaction_id"
        )

    return {
        "pending_transaction": None,

        "answer": (
            f"Transaction "
            f"{transaction_id or ''} "
            f"was cancelled. "
            f"No money was transferred."
        )
    }


async def unknown_request(
    state: AgentState
) -> dict:

    return {
        "answer": (
            "I can help you with:\n\n"
            "1. Checking a transaction status\n"
            "2. Making a new bank transfer"
        )
    }


async def final_response(
    state: AgentState
) -> dict:

    answer = state.get(
        "answer",
        "Request completed."
    )

    return {
        "messages": [
            AIMessage(
                content=answer
            )
        ],

        "answer": answer
    }