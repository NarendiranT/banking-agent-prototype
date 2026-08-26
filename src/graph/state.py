from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    user_name: str | None
    intent: str
    pin: str | None
    transaction_id: str | None
    source_account: str | None
    destination_account: str | None
    amount: float | None
    pending_transaction: dict | None
    approval_status: str | None
    auth_verified: bool
    transaction_result: dict | None
    account_result: dict | None
    answer: str
