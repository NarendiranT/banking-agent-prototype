# Banking Agent

LangGraph banking assistant with FastAPI, Streamlit, and FastMCP. Check transaction status or send a transfer. The graph pauses for PIN identity, transaction ID lookup, and payment approval.

## Setup

Python 3.11+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
python run.py all
```

| Service | URL |
| --- | --- |
| Streamlit UI | http://localhost:8501 |
| FastAPI | http://localhost:8000 |
| MCP tools | http://localhost:8001/mcp |

Open http://localhost:8501 to chat.

## Demo accounts

| User | PIN | Account | Balance |
| --- | --- | --- | --- |
| John Doe | `1234` | `ACC001` | ₹100,000 |
| David | `5678` | `ACC002` | ₹50,000 |

Sample transaction: `TXN1001` — ₹5,000 from `ACC001` to `ACC002`, `SUCCESS`.

## Example chat

Use a new conversation (sidebar **New Conversation**) between examples so identity is asked again.

### Greeting

```text
hello
```

### Transaction status

```text
What is the status of my transaction?
```

1. Account ID: `ACC001`, PIN: `1234`, **Continue**
2. Transaction ID: `TXN1001`, **Look up status**

### Transfer (approve)

```text
Transfer 2500 to ACC002
```

1. Account ID: `ACC001`, PIN: `1234`, **Continue**
2. Review from/to/amount, enter PIN `1234`, **Approve Transaction**

PIN and account can also go in the message:

```text
Transfer 2500 to ACC002 pin 1234 from ACC001
```

### Transfer (reject)

```text
Send 15000 to ACC002
```

Identify with `ACC001` / `1234`, then **Reject Transaction**.

### Second user

```text
Transfer 1500 to ACC001 pin 5678 from ACC002
```

Approve with PIN `5678`.

### Validation errors

```text
Transfer 100 to ACC999 pin 1234 from ACC001
Transfer 100 to ACC001 pin 1234 from ACC001
```
