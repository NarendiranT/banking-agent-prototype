import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8001")