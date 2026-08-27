from __future__ import annotations

import uuid

import requests
import streamlit as st

from config import API_BASE_URL
from telemetry import setup_telemetry

setup_telemetry("banking-ui")

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
if "awaiting_pin" not in st.session_state:
    st.session_state.awaiting_pin = False
if "awaiting_txn_id" not in st.session_state:
    st.session_state.awaiting_txn_id = False
if "pending_txn_id" not in st.session_state:
    st.session_state.pending_txn_id = ""
if "approval_error" not in st.session_state:
    st.session_state.approval_error = None

st.title("🏦 Banking Assistant")
st.caption(f"Conversation ID: {st.session_state.thread_id}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

pending = st.session_state.pending_transaction

if st.session_state.awaiting_pin and not pending:
    st.divider()
    st.subheader("Identify your account")
    st.info(
        "Enter your account ID and PIN so the assistant "
        "can use your source account."
    )
    identity_account = st.text_input(
        "Enter Account ID",
        placeholder="ACC001",
        key="identity_account",
    )
    identity_pin = st.text_input(
        "Enter Account PIN",
        type="password",
        max_chars=4,
        key="identity_pin",
    )
    if st.session_state.approval_error:
        st.error(st.session_state.approval_error)

    if st.button("Continue", use_container_width=True, type="primary"):
        if not identity_account:
            st.session_state.approval_error = "Please enter your account ID."
            st.rerun()
        if not identity_pin:
            st.session_state.approval_error = "Please enter your PIN."
            st.rerun()
        try:
            response = requests.post(
                f"{API_BASE_URL}/identify",
                json={
                    "thread_id": st.session_state.thread_id,
                    "pin": identity_pin,
                    "account_id": identity_account.strip().upper(),
                },
                timeout=30,
            )
            data = response.json()
            if response.status_code != 200:
                st.session_state.approval_error = data.get(
                    "detail",
                    "PIN verification failed.",
                )
                st.rerun()

            if data.get("status") == "txn_id_required":
                st.session_state.awaiting_pin = False
                st.session_state.awaiting_txn_id = True
                st.session_state.pending_txn_id = (
                    data.get("transaction_id") or ""
                )
                st.session_state.pop("lookup_txn_id", None)
                st.session_state.approval_error = None
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data.get(
                        "message",
                        "Enter the transaction ID to look up.",
                    ),
                })
                st.rerun()

            if data.get("status") == "approval_required":
                st.session_state.awaiting_pin = False
                st.session_state.approval_error = None
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data.get(
                        "message",
                        "This transaction requires your approval.",
                    ),
                })
                transaction = data["transaction"]
                st.session_state.pending_transaction = {
                    "transaction_id": transaction["transaction_id"],
                    "source_account": transaction["source_account"],
                    "destination_account": transaction["destination_account"],
                    "amount": transaction["amount"],
                }
                st.rerun()

            st.session_state.awaiting_pin = False
            st.session_state.approval_error = None
            st.session_state.messages.append({
                "role": "assistant",
                "content": data.get("message", "Account identified."),
            })
            st.rerun()
        except requests.RequestException:
            st.session_state.approval_error = (
                "Unable to communicate with banking service."
            )
            st.rerun()

if (
    st.session_state.awaiting_txn_id
    and not pending
    and not st.session_state.awaiting_pin
):
    st.divider()
    st.subheader("Transaction status")
    st.info("Confirm the transaction ID to look up.")
    if "lookup_txn_id" not in st.session_state:
        st.session_state.lookup_txn_id = st.session_state.pending_txn_id
    lookup_txn_id = st.text_input(
        "Enter Transaction ID",
        placeholder="TXN1001",
        key="lookup_txn_id",
    )
    if st.session_state.approval_error:
        st.error(st.session_state.approval_error)

    if st.button("Look up status", use_container_width=True, type="primary"):
        if not lookup_txn_id:
            st.session_state.approval_error = "Please enter a transaction ID."
            st.rerun()
        try:
            response = requests.post(
                f"{API_BASE_URL}/lookup",
                json={
                    "thread_id": st.session_state.thread_id,
                    "transaction_id": lookup_txn_id.strip().upper(),
                },
                timeout=30,
            )
            data = response.json()
            if response.status_code != 200:
                st.session_state.approval_error = data.get(
                    "detail",
                    "Transaction lookup failed.",
                )
                st.rerun()
            st.session_state.awaiting_txn_id = False
            st.session_state.pending_txn_id = ""
            st.session_state.pop("lookup_txn_id", None)
            st.session_state.approval_error = None
            st.session_state.messages.append({
                "role": "assistant",
                "content": data.get(
                    "message",
                    "Transaction status lookup completed.",
                ),
            })
            st.rerun()
        except requests.RequestException:
            st.session_state.approval_error = (
                "Unable to communicate with banking service."
            )
            st.rerun()

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

    st.write("**Pending Transaction ID**")
    st.code(pending["transaction_id"])
    pin = st.text_input(
        "Enter Transaction PIN",
        type="password",
        max_chars=4,
        key="transaction_pin",
    )
    if st.session_state.approval_error:
        st.error(st.session_state.approval_error)

    approve_col, reject_col = st.columns(2)
    with approve_col:
        if st.button(
            "✅ Approve Transaction",
            use_container_width=True,
            type="primary",
        ):
            if not pin:
                st.session_state.approval_error = "Please enter your PIN."
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
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": data.get(
                            "message",
                            "Transaction completed successfully.",
                        ),
                    })
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
        if st.button("❌ Reject Transaction", use_container_width=True):
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
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data.get("message", "Transaction cancelled."),
                })
                st.session_state.pending_transaction = None
                st.session_state.approval_error = None
                st.rerun()
            except requests.RequestException:
                st.session_state.approval_error = (
                    "Unable to communicate with banking service."
                )
                st.rerun()

user_input = st.chat_input(
    "Ask about a balance, transaction, or make a payment..."
)

if user_input:
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
    })
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
            st.session_state.messages.append({
                "role": "assistant",
                "content": assistant_message,
            })
            with st.chat_message("assistant"):
                st.markdown(assistant_message)
        elif data["status"] == "pin_required":
            assistant_message = data.get(
                "message",
                "Enter your PIN and account ID to identify your account.",
            )
            st.session_state.messages.append({
                "role": "assistant",
                "content": assistant_message,
            })
            st.session_state.awaiting_pin = True
            st.session_state.approval_error = None
            st.rerun()
        elif data["status"] == "txn_id_required":
            assistant_message = data.get(
                "message",
                "Enter the transaction ID to look up.",
            )
            st.session_state.messages.append({
                "role": "assistant",
                "content": assistant_message,
            })
            st.session_state.awaiting_txn_id = True
            st.session_state.pending_txn_id = data.get("transaction_id") or ""
            st.session_state.pop("lookup_txn_id", None)
            st.session_state.approval_error = None
            st.rerun()
        elif data["status"] == "approval_required":
            assistant_message = data.get(
                "message",
                "This transaction requires your approval.",
            )
            st.session_state.messages.append({
                "role": "assistant",
                "content": assistant_message,
            })
            st.session_state.pending_transaction = {
                "transaction_id": data["transaction"]["transaction_id"],
                "source_account": data["transaction"]["source_account"],
                "destination_account": (
                    data["transaction"]["destination_account"]
                ),
                "amount": data["transaction"]["amount"],
            }
            st.rerun()
    except requests.RequestException:
        st.error("Unable to communicate with the backend.")

with st.sidebar:
    st.header("Session")
    st.write("Thread ID")
    st.code(st.session_state.thread_id)
    if st.button("New Conversation", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.pending_transaction = None
        st.session_state.awaiting_pin = False
        st.session_state.awaiting_txn_id = False
        st.session_state.pending_txn_id = ""
        st.session_state.pop("lookup_txn_id", None)
        st.session_state.approval_error = None
        st.rerun()