import aiosqlite
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from graph.nodes import (
    approval_node,
    cancel_transaction,
    conversation_agent,
    execute_transaction,
    final_response,
    risk_check,
    transaction_status,
    unknown_request,
    validate_transaction,
)
from graph.routes import (
    approval_router,
    intent_router,
    validation_router,
)
from graph.state import AgentState

ROOT_DIR = Path(__file__).resolve().parents[2]
CHECKPOINT_PATH = ROOT_DIR / "langgraph_checkpoints.db"

workflow = StateGraph(AgentState)

workflow.add_node("conversation_agent", conversation_agent)
workflow.add_node("transaction_status", transaction_status)
workflow.add_node("validate_transaction", validate_transaction)
workflow.add_node("risk_check", risk_check)
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
        "status": "transaction_status",
        "transfer": "validate_transaction",
        "unknown": "unknown_request",
    },
)

workflow.add_edge("transaction_status", "final_response")

workflow.add_conditional_edges(
    "validate_transaction",
    validation_router,
    {
        "valid": "risk_check",
        "failed": "final_response",
    },
)

workflow.add_edge("risk_check", "approval")

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
