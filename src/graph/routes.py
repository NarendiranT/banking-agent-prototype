from graph.state import AgentState


def intent_router(state: AgentState) -> str:
    intent = state.get("intent")
    if intent == "status":
        return "status"
    if intent == "balance":
        return "balance"
    if intent == "transfer":
        return "transfer"
    return "unknown"


def account_router(state: AgentState) -> str:
    if state.get("intent") == "account_setup_failed":
        return "failed"
    if state.get("intent") == "status":
        return "status"
    if state.get("intent") == "balance":
        return "balance"
    return "transfer"


def validation_router(state: AgentState) -> str:
    if state.get("intent") == "validation_failed":
        return "failed"
    return "valid"


def approval_router(state: AgentState) -> str:
    if (
        state.get("approval_status") == "approved"
        and state.get("auth_verified")
    ):
        return "execute"
    return "cancel"
