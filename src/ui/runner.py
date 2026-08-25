"""Launch the Streamlit banking UI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
APP_PATH = Path(__file__).resolve().parent / "streamlit_app.py"


def run() -> None:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    )
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(APP_PATH),
                "--server.port",
                "8501",
                "--server.headless",
                "true",
            ],
            env=env,
        )
    )


if __name__ == "__main__":
    run()
