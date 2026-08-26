import re
import uuid

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from graph.state import AgentState
from mcp.mcp_client import (
    mcp_execute_transaction,
    mcp_get_account_by_pin,
    mcp_get_transaction_status,
    mcp_validate_account,
)


async def conversation_agent(state: AgentState) -> dict:
    message = state["messages"][-1].content
    if isinstance(message, list):
        text = message[0]["text"].lower()
    else:
        text = message.lower()
    identity = _identity_from_text(text)

    if "status" in text or ("transaction" in text and "check" in text):
        result = {"intent": "status", **identity}
        match = re.search(r"(TXN[\w\d]+)", message, re.IGNORECASE)
        if match:
            result["transaction_id"] = match.group(1).upper()
        return result

    if "transfer" in text or "send" in text or "pay" in text:
        account_match = re.search(
            r"(?:to|into)\s+(ACC[\w\d]+)|(ACC[\w\d]+)",
            message,
            re.IGNORECASE,
        )
        amount_match = re.search(r"[₹]?\s*([\d,]+(?:\.\d+)?)", message)
        if account_match and amount_match:
            destination = (
                account_match.group(1) or account_match.group(2)
            ).upper()
            amount = float(amount_match.group(1).replace(",", ""))
            return {
                "intent": "transfer",
                "destination_account": destination,
                "amount": amount,
                **identity,
            }

    return {"intent": "unknown"}


def _identity_from_text(text: str) -> dict:
    result = {}
    pin_match = re.search(r"\b(?:pin|PIN)\s*[:=]?\s*(\d{4,6})\b", text)
    if pin_match:
        result["pin"] = pin_match.group(1)

    from_match = re.search(
        r"\b(?:from|account)\s+(ACC[\w\d]+)",
        text,
        re.IGNORECASE,
    )
    if from_match:
        result["source_account"] = from_match.group(1).upper()
    return result


def _resume_field(resume, *keys) -> str:
    if isinstance(resume, dict):
        for key in keys:
            value = resume.get(key)
            if value:
                return str(value).strip()
        return ""
    return str(resume or "").strip()


async def set_user_account(state: AgentState) -> dict:
    if state.get("source_account") and state.get("user_id"):
        return {}

    pin = (state.get("pin") or "").strip()
    account_id = (state.get("source_account") or "").strip()
    if not pin or not account_id:
        resume = interrupt({
            "type": "set_user_account",
            "message": (
                "Enter your PIN and account ID "
                "to identify your source account."
            ),
        })
        pin = pin or _resume_field(resume, "pin")
        account_id = account_id or _resume_field(
            resume,
            "account_id",
            "source_account",
        )

    account_id = account_id.upper()
    if len(pin) < 4 or not account_id:
        return {
            "answer": (
                "A PIN and account ID are required to identify your account."
            ),
            "intent": "account_setup_failed",
            "pin": None,
        }

    account = await mcp_get_account_by_pin(pin, account_id)
    if not account:
        return {
            "answer": "Invalid PIN. I could not identify your account.",
            "intent": "account_setup_failed",
            "pin": None,
        }

    if account.get("is_locked"):
        return {
            "answer": (
                "This account is locked after too many failed PIN attempts."
            ),
            "intent": "account_setup_failed",
            "pin": None,
        }

    matched_account_id = account.get("account_id")
    if not matched_account_id:
        return {
            "answer": (
                "PIN and account ID do not match, "
                "or the account is not active."
            ),
            "intent": "account_setup_failed",
            "pin": None,
        }

    return {
        "user_id": account["user_id"],
        "user_name": account.get("name"),
        "source_account": matched_account_id,
        "auth_verified": True,
        "pin": None,
    }


async def transaction_status(state: AgentState) -> dict:
    transaction_id = (state.get("transaction_id") or "").strip()
    resume = interrupt({
        "type": "transaction_status",
        "message": (
            "Enter the transaction ID to look up (for example TXN1001)."
        ),
        "transaction_id": transaction_id or None,
        "source_account": state.get("source_account"),
    })
    transaction_id = (
        _resume_field(resume, "transaction_id") or transaction_id
    ).upper()

    if not transaction_id:
        return {
            "answer": (
                "A transaction ID is required to look up transfer status."
            ),
        }

    transaction = await mcp_get_transaction_status(transaction_id)
    if not transaction:
        return {
            "answer": f"I could not find transaction {transaction_id}.",
        }

    source_account = state.get("source_account")
    if source_account and source_account not in (
        transaction.get("source_account"),
        transaction.get("destination_account"),
    ):
        return {
            "answer": (
                f"Transaction {transaction_id} is not associated "
                f"with account {source_account}."
            ),
        }

    return {
        "transaction_id": transaction_id,
        "transaction_result": transaction,
        "answer": (
            f"Transaction {transaction['transaction_id']} "
            f"for ₹{transaction['amount']:,.2f} is currently "
            f"{transaction['status']}."
        ),
    }


async def validate_transaction(state: AgentState) -> dict:
    source = state["source_account"]
    destination = state["destination_account"]
    amount = state["amount"]

    if amount <= 0:
        return {
            "answer": "Transaction amount must be greater than zero.",
            "intent": "validation_failed",
        }

    if source == destination:
        return {
            "answer": (
                "Source and destination accounts cannot be the same."
            ),
            "intent": "validation_failed",
        }

    account = await mcp_validate_account(destination)
    if not account:
        return {
            "answer": f"Account {destination} was not found.",
            "intent": "validation_failed",
        }

    if account["status"] != "ACTIVE":
        return {
            "answer": "Destination account is not active.",
            "intent": "validation_failed",
        }

    transaction_id = "PENDING_" + uuid.uuid4().hex[:8].upper()
    return {
        "pending_transaction": {
            "transaction_id": transaction_id,
            "source_account": source,
            "destination_account": destination,
            "amount": amount,
            "user_id": state.get("user_id"),
            "status": "PENDING_APPROVAL",
        },
    }


async def approval_node(state: AgentState) -> dict:
    pending = state["pending_transaction"]
    approval = interrupt({
        "type": "transaction_approval",
        "transaction": pending,
    })

    if not approval.get("approved", False):
        return {
            "approval_status": "rejected",
            "auth_verified": False,
        }

    return {
        "approval_status": "approved",
        "auth_verified": approval.get(
            "auth_verified",
            state.get("auth_verified", False),
        ),
    }


async def execute_transaction(state: AgentState) -> dict:
    if not state.get("auth_verified"):
        return {"answer": "Transaction authentication failed."}

    pending = state["pending_transaction"]
    result = await mcp_execute_transaction(
        transaction_id=pending["transaction_id"],
        source_account=pending["source_account"],
        destination_account=pending["destination_account"],
        amount=pending["amount"],
        user_id=state["user_id"],
    )

    if not result.get("success"):
        return {
            "transaction_result": result,
            "answer": result.get("message", "Transaction failed."),
        }

    return {
        "transaction_result": result,
        "pending_transaction": None,
        "answer": (
            f"Transaction completed successfully.\n\n"
            f"Transaction ID: {result['transaction_id']}\n\n"
            f"Amount: ₹{result['amount']:,.2f}"
        ),
    }


async def cancel_transaction(state: AgentState) -> dict:
    pending = state.get("pending_transaction")
    transaction_id = pending.get("transaction_id") if pending else None
    return {
        "pending_transaction": None,
        "answer": (
            f"Transaction {transaction_id or ''} was cancelled. "
            f"No money was transferred."
        ),
    }


async def unknown_request(state: AgentState) -> dict:
    return {
        "answer": (
            "I can help you with:\n\n"
            "1. Checking a transaction status\n"
            "2. Making a new bank transfer"
        ),
    }


async def final_response(state: AgentState) -> dict:
    answer = state.get("answer", "Request completed.")
    return {
        "messages": [AIMessage(content=answer)],
        "answer": answer,
    }
