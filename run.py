#!/usr/bin/env python3
"""Start Banking Agent services: api, ui, mcp, or all."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

COMMANDS = {
    "api": [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
        "--app-dir",
        str(SRC),
    ],
    "ui": [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(SRC / "ui" / "streamlit_app.py"),
        "--server.port",
        "8501",
        "--server.headless",
        "true",
    ],
    "mcp": [
        sys.executable,
        "-m",
        "mcp.server",
    ],
}


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(SRC) if not existing else f"{SRC}{os.pathsep}{existing}"
    )
    return env


def run_one(name: str) -> int:
    print(f"Starting {name}...")
    return subprocess.call(COMMANDS[name], cwd=ROOT, env=build_env())


def run_all() -> int:
    processes: list[subprocess.Popen] = []
    try:
        for name, command in COMMANDS.items():
            print(f"Starting {name}...")
            processes.append(
                subprocess.Popen(command, cwd=ROOT, env=build_env())
            )
        return_code = 0
        for process in processes:
            code = process.wait()
            if code:
                return_code = code
        return return_code
    except KeyboardInterrupt:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Banking Agent UI, FastAPI, and MCP services."
    )
    parser.add_argument(
        "service",
        choices=["api", "ui", "mcp", "all"],
        help=(
            "Service to start: FastAPI (api), Streamlit UI (ui), "
            "MCP server (mcp), or all."
        ),
    )
    args = parser.parse_args()

    if args.service == "all":
        return run_all()
    return run_one(args.service)


if __name__ == "__main__":
    raise SystemExit(main())
