import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8001")


def _data_path(env_name: str, filename: str) -> Path:
    raw = os.getenv(env_name)
    if not raw:
        return ROOT_DIR / "data" / filename
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


DATA_DIR = ROOT_DIR / "data"
BANKING_DB_PATH = _data_path("BANKING_DB_PATH", "banking.db")
CHECKPOINT_PATH = _data_path("CHECKPOINT_PATH", "langgraph_checkpoints.db")
