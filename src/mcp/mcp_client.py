from backend.service import (
    get_transaction_status,
    get_account,
    get_user_account_by_pin,
    transfer_money,
)


async def mcp_get_transaction_status(
    transaction_id: str
):

    # Later replace this with real MCP call
    return await get_transaction_status(
        transaction_id
    )


async def mcp_get_account_by_pin(
    pin: str,
    account_id: str | None = None,
):
    return await get_user_account_by_pin(pin, account_id)


async def mcp_validate_account(
    account_id: str
):

    # Later replace this with real MCP call
    return await get_account(
        account_id
    )


async def mcp_execute_transaction(
    transaction_id: str,
    source_account: str,
    destination_account: str,
    amount: float,
    user_id: str,
):

    # Later this becomes MCP server tool invocation

    return await transfer_money(
        transaction_id=
            transaction_id,

        source_account=
            source_account,

        destination_account=
            destination_account,

        amount=
            amount,

        user_id=
            user_id
    )