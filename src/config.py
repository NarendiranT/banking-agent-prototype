import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8001")
BANKING_DB_PATH = os.getenv("BANKING_DB_PATH", "data/banking.db")
CHECKPOINT_PATH = os.getenv("CHECKPOINT_PATH", "data/langgraph_checkpoints.db")
