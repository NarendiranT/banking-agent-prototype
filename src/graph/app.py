import aiosqlite

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.graph.state import AgentState

from app.graph.nodes import (
    conversation_agent,
    transaction_status,
    validate_transaction,
    risk_check,
    approval_node,
    execute_transaction,
    cancel_transaction,
    unknown_request,
    final_response,
)

from app.graph.router import (
    intent_router,
    validation_router,
    approval_router,
)


workflow = StateGraph(AgentState)


workflow.add_node(
    "conversation_agent",
    conversation_agent
)

workflow.add_node(
    "transaction_status",
    transaction_status
)

workflow.add_node(
    "validate_transaction",
    validate_transaction
)

workflow.add_node(
    "risk_check",
    risk_check
)

workflow.add_node(
    "approval",
    approval_node
)

workflow.add_node(
    "execute_transaction",
    execute_transaction
)

workflow.add_node(
    "cancel_transaction",
    cancel_transaction
)

workflow.add_node(
    "unknown_request",
    unknown_request
)

workflow.add_node(
    "final_response",
    final_response
)


workflow.add_edge(
    START,
    "conversation_agent"
)


workflow.add_conditional_edges(
    "conversation_agent",
    intent_router,
    {
        "status": "transaction_status",
        "transfer": "validate_transaction",
        "unknown": "unknown_request",
    }
)


workflow.add_edge(
    "transaction_status",
    "final_response"
)


workflow.add_conditional_edges(
    "validate_transaction",
    validation_router,
    {
        "valid": "risk_check",
        "failed": "final_response",
    }
)


workflow.add_edge(
    "risk_check",
    "approval"
)


workflow.add_conditional_edges(
    "approval",
    approval_router,
    {
        "execute": "execute_transaction",
        "cancel": "cancel_transaction",
    }
)


workflow.add_edge(
    "execute_transaction",
    "final_response"
)

workflow.add_edge(
    "cancel_transaction",
    "final_response"
)

workflow.add_edge(
    "unknown_request",
    "final_response"
)

workflow.add_edge(
    "final_response",
    END
)


async def create_graph():

    connection = await aiosqlite.connect(
        "langgraph_checkpoints.db"
    )

    checkpointer = AsyncSqliteSaver(
        connection
    )

    await checkpointer.setup()

    graph = workflow.compile(
        checkpointer=checkpointer
    )

    return graph, connection