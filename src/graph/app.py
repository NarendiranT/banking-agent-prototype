import sys
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from config import CHECKPOINT_PATH  # noqa: E402
from graph.nodes import (  # noqa: E402
    approval_node,
    cancel_transaction,
    conversation_agent,
    execute_transaction,
    final_response,
    set_user_account,
    transaction_status,
    unknown_request,
    validate_transaction,
)
from graph.routes import (  # noqa: E402
    account_router,
    approval_router,
    intent_router,
    validation_router,
)
from graph.state import AgentState  # noqa: E402

workflow = StateGraph(AgentState)

workflow.add_node("conversation_agent", conversation_agent)
workflow.add_node("set_user_account", set_user_account)
workflow.add_node("transaction_status", transaction_status)
workflow.add_node("validate_transaction", validate_transaction)
workflow.add_node("approval", approval_node)
workflow.add_node("execute_transaction", execute_transaction)
workflow.add_node("cancel_transaction", cancel_transaction)
workflow.add_node("unknown_request", unknown_request)
workflow.add_node("final_response", final_response)

workflow.add_edge(START, "conversation_agent")

workflow.add_conditional_edges(
    "conversation_agent",
    intent_router,
    {
        "status": "set_user_account",
        "transfer": "set_user_account",
        "unknown": "unknown_request",
    },
)

workflow.add_conditional_edges(
    "set_user_account",
    account_router,
    {
        "status": "transaction_status",
        "transfer": "validate_transaction",
        "failed": "final_response",
    },
)

workflow.add_edge("transaction_status", "final_response")

workflow.add_conditional_edges(
    "validate_transaction",
    validation_router,
    {
        "valid": "approval",
        "failed": "final_response",
    },
)

workflow.add_conditional_edges(
    "approval",
    approval_router,
    {
        "execute": "execute_transaction",
        "cancel": "cancel_transaction",
    },
)

workflow.add_edge("execute_transaction", "final_response")
workflow.add_edge("cancel_transaction", "final_response")
workflow.add_edge("unknown_request", "final_response")
workflow.add_edge("final_response", END)

_runtime_graph = None
_connection = None

# Used by LangGraph Studio via langgraph.json. FastAPI replaces this
# with a checkpointer-backed graph in init_runtime_graph().
graph = workflow.compile()


async def init_runtime_graph():
    global _runtime_graph, _connection, graph

    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _connection = await aiosqlite.connect(str(CHECKPOINT_PATH))
    checkpointer = AsyncSqliteSaver(_connection)
    await checkpointer.setup()
    _runtime_graph = workflow.compile(checkpointer=checkpointer)
    graph = _runtime_graph
    return _runtime_graph


def get_graph():
    if _runtime_graph is None:
        raise RuntimeError(
            "Graph is not initialized. Call init_runtime_graph() first."
        )
    return _runtime_graph


async def close_graph():
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
