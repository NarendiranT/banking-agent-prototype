---
name: senior-python-developer
description: Applies senior Python judgment to this banking agent — FastAPI, LangGraph, FastMCP, Streamlit, async aiosqlite, PIN handling, money, and OpenTelemetry. Use when writing, reviewing, refactoring, or debugging Python in this repository.
---

# Senior Python developer

Work in this repo as a senior on the banking agent. Python 3.11+. Change the smallest surface that solves the task, match the file you are editing, and leave neighboring style alone.

## Layout

Code lives in `src/`. Imports are absolute top-level names because `PYTHONPATH=src` and the package dir is `src`:

`backend`, `graph`, `mcp_server`, `ui`, `config`, `telemetry`.

`graph/app.py` inserts `src` on `sys.path` because LangGraph loads it as a script. Copy that only for a module loaded the same way.

Add a dependency to both `pyproject.toml` `[project].dependencies` and `requirements.txt`. They are duplicated and must stay in sync. Require `>=3.11` features (`list[str]`, `str | None`). Add `from __future__ import annotations` only in modules that already have it.

## Where code goes

| Work | Home |
| --- | --- |
| SQL, accounts, PIN, transfers | `backend/service.py`, schema in `backend/database_db.py` |
| HTTP, Pydantic bodies, thread locks, graph resume | `backend/main.py` |
| Intent parsing, interrupts, partial state updates | `graph/nodes.py` |
| Conditional edges | `graph/routes.py` |
| New state fields | `graph/state.py` `AgentState` first |
| Wiring a node into the graph | `graph/app.py`, wrapped with `traced_graph_node` |
| Tool the graph calls | `mcp_server/mcp_client.py` (in-process wrapper over `backend.service`) |
| Tool exposed on the MCP server | `mcp_server/server.py` `@mcp.tool`, same service function |
| Chat UI | `ui/streamlit_app.py`, HTTP to `API_BASE_URL` only |
| Paths and app env | `config.py` |
| Spans and metrics | `telemetry.py` |

Graph nodes call `mcp_server.mcp_client`. They do not import `backend.service` or open SQLite. The UI does not import `backend` or `graph`. FastAPI routes do not contain SQL.

Read app settings from `config`: `BANKING_DB_PATH`, `CHECKPOINT_PATH`, `API_BASE_URL`, `MCP_BASE_URL`. `telemetry.py` owns `OTEL_*`. A new app env var goes in `config.py`, `.env.example`, and the README table.

## Banking behavior to preserve

Service functions return `dict | None` or `{success, message}` for business failures. They do not raise for "account missing", "inactive", or "insufficient balance". `transfer_money` uses `BEGIN IMMEDIATE`, treats `transaction_id` as `idempotency_key`, rolls back on failure, and writes currency `INR`. A new transfer path keeps that contract so nodes and MCP tools stay unchanged.

`verify_pin` locks the user at 3 failed attempts (`is_locked = 1`) and resets the counter on success. Account lookup accepts a PIN of 4–6 digits; `IdentifyRequest` and `ApprovalRequest` already constrain that.

`AgentState` is a `total=False` `TypedDict`. Nodes return a partial dict of its keys. Human pauses use `interrupt` from `langgraph.types`. Resume values go through `_resume_field`. Declare a new key on `AgentState` before any node reads it.

`@traced` is async-only. Put `@traced("banking.<operation>")` on new service operations and call `set_span_attributes` with the existing `banking.*` keys (`source_account`, `destination_account`, `user_id`, `transaction_id`, `amount`, `pin_valid`, `account_found`, `transaction_found`, `transaction_status`, `transfer_success`, `idempotent`, `failed_pin_attempts`). Register a new graph node with `traced_graph_node` in `graph/app.py`. Let `GraphInterrupt` propagate; `traced` and `traced_graph_node` already re-raise interrupt exceptions.

## Security

Never put a PIN, `pin_hash`, or `.env` value in a log, span, exception message, or API response. `set_span_attributes` will record whatever you pass. `traced_graph_node` copies `intent`, `source_account`, and `user_id` only — do not add `pin`.

Compare PINs with `bcrypt.checkpw` against `pin_hash`. Store new hashes with `bcrypt.hashpw`. SQL uses `?` placeholders.

`bcrypt` is blocking. Call it from async code with `asyncio.to_thread`. Do not add `time.sleep`, sync `requests`, or other blocking I/O on the API, graph, or MCP event loop. Sync `requests` stays in `ui/`, where Streamlit is synchronous.

## Money

Balances, `AgentState.amount`, and the SQLite `amount` column are floats today. Leave that schema in place unless the task is money correctness. Do not add new binary-float arithmetic (fees, splits, rounded comparisons). When amount handling must change, parse with `Decimal(str(value))`, never `Decimal(float_value)`, and convert at the existing float boundary.

## Async SQLite

One `async with aiosqlite.connect(...)` per operation. Set `row_factory = aiosqlite.Row`. `commit` after writes. `rollback` on failure. Transfers keep `BEGIN IMMEDIATE` so concurrent debits cannot both pass the balance check.

## API edge

Request bodies are Pydantic v2 `BaseModel`s with `Field` constraints, next to the other models in `backend/main.py`. Validate shape there. Domain rules stay in `backend/service.py`. HTTP failures use `HTTPException`. Per-thread graph access stays under `thread_locks`.

## How to change code

- Match quotes, import order (stdlib, third party, local), and wrapping of the surrounding file.
- Annotate new public functions. Skip a type rewrite of untyped neighbors.
- Docstrings only where the module or function already uses them, or where the name does not say what it does. `telemetry.py` has a module docstring; most functions do not.
- A behavior change that can fail silently gets a pytest test under `tests/`. There is no suite yet. Add `pytest` (and `pytest-asyncio` for async tests) to both dependency files when you introduce the first test. Skip a framework for a one-line fix.
- After editing, run the narrowest check that exercises the change: `python -c` import, a single pytest, or `make api` / `make mcp` / `make ui` when the HTTP or UI path changed. `make install` if dependencies changed.

## Review

On a review, report only issues you can point at in the diff:

- SQL built with f-strings or string concatenation
- PIN or `pin_hash` leaving the process boundary (logs, spans, error text)
- New blocking calls inside `async def` on the API, graph, or MCP path
- SQL or `backend.service` imports inside `graph/nodes.py` or `ui/`
- A state key read by a node and missing from `AgentState`
- A dependency added to only one of `pyproject.toml` and `requirements.txt`
- A new app env var missing from `config.py`, `.env.example`, and the README
- A business failure in a transfer path that raises instead of returning `{success: False, message}`
- A new graph node registered without `traced_graph_node`
