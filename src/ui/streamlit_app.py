from __future__ import annotations

import uuid
import requests
import streamlit as st

# from src.config import API_BASE_URL
API_BASE_URL = "http://localhost:8000"
st.set_page_config(
    page_title="Banking Assistant",
    page_icon="🏦",
    layout="centered",
)


if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_transaction" not in st.session_state:
    st.session_state.pending_transaction = None

if "approval_error" not in st.session_state:
    st.session_state.approval_error = None


st.title("🏦 Banking Assistant")

st.caption(
    f"Conversation ID: {st.session_state.thread_id}"
)


for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


pending = st.session_state.pending_transaction

if pending:

    st.divider()

    st.subheader("Transaction Approval Required")

    st.warning(
        "Please review the transaction and enter your PIN before approving."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.write("**From Account**")
        st.write(pending["source_account"])

        st.write("**Amount**")
        st.write(f"₹{pending['amount']:,.2f}")

    with col2:
        st.write("**To Account**")
        st.write(pending["destination_account"])

        st.write("**Risk Level**")
        st.write(pending.get("risk_level", "UNKNOWN"))

    st.write("**Pending Transaction ID**")

    st.code(
        pending["transaction_id"]
    )

    pin = st.text_input(
        "Enter Transaction PIN",
        type="password",
        max_chars=6,
        key="transaction_pin",
    )

    if st.session_state.approval_error:

        st.error(
            st.session_state.approval_error
        )

    approve_col, reject_col = st.columns(2)


    with approve_col:

        if st.button(
            "✅ Approve Transaction",
            use_container_width=True,
            type="primary",
        ):

            if not pin:

                st.session_state.approval_error = (
                    "Please enter your PIN."
                )

                st.rerun()

            try:

                response = requests.post(
                    f"{API_BASE_URL}/approve",
                    json={
                        "thread_id": st.session_state.thread_id,
                        "transaction_id": pending["transaction_id"],
                        "pin": pin,
                    },
                    timeout=30,
                )

                data = response.json()

                if response.status_code == 200:

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": data.get(
                                "message",
                                "Transaction completed successfully.",
                            ),
                        }
                    )

                    st.session_state.pending_transaction = None
                    st.session_state.approval_error = None

                    st.rerun()

                else:

                    st.session_state.approval_error = data.get(
                        "detail",
                        "PIN verification failed.",
                    )

                    st.rerun()

            except requests.RequestException:

                st.session_state.approval_error = (
                    "Unable to communicate with banking service."
                )

                st.rerun()


    with reject_col:

        if st.button(
            "❌ Reject Transaction",
            use_container_width=True,
        ):

            try:

                response = requests.post(
                    f"{API_BASE_URL}/reject",
                    json={
                        "thread_id": st.session_state.thread_id,
                        "transaction_id": pending["transaction_id"],
                    },
                    timeout=30,
                )

                data = response.json()

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": data.get(
                            "message",
                            "Transaction cancelled.",
                        ),
                    }
                )

                st.session_state.pending_transaction = None
                st.session_state.approval_error = None

                st.rerun()

            except requests.RequestException:

                st.session_state.approval_error = (
                    "Unable to communicate with banking service."
                )

                st.rerun()



user_input = st.chat_input(
    "Ask about a transaction or make a payment..."
)


if user_input:

    # Add user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    try:


        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "thread_id": st.session_state.thread_id,
                "message": user_input,
            },
            timeout=30,
        )

        data = response.json()


        if data["status"] == "completed":

            assistant_message = data["message"]

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message,
                }
            )

            with st.chat_message("assistant"):
                st.markdown(assistant_message)


        elif data["status"] == "approval_required":

            assistant_message = data.get(
                "message",
                "This transaction requires your approval.",
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message,
                }
            )

            st.session_state.pending_transaction = {
                "transaction_id": data["transaction"]["transaction_id"],
                "source_account": data["transaction"]["source_account"],
                "destination_account": data["transaction"]["destination_account"],
                "amount": data["transaction"]["amount"],
                "risk_level": data["transaction"].get(
                    "risk_level",
                    "LOW",
                ),
            }

            st.rerun()

    except requests.RequestException:

        st.error(
            "Unable to communicate with the backend."
        )


with st.sidebar:

    st.header("Session")

    st.write("Thread ID")

    st.code(
        st.session_state.thread_id
    )

    if st.button(
        "New Conversation",
        use_container_width=True,
    ):

        st.session_state.thread_id = str(uuid.uuid4())

        st.session_state.messages = []

        st.session_state.pending_transaction = None

        st.session_state.approval_error = None

        st.rerun()