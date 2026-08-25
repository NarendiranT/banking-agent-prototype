PYTHON ?= python3
export PYTHONPATH := src

.PHONY: help install api ui mcp run

help:
	@echo "Banking Agent commands"
	@echo "  make install   Install Python dependencies"
	@echo "  make api       Run FastAPI on http://localhost:8000"
	@echo "  make ui        Run Streamlit UI on http://localhost:8501"
	@echo "  make mcp       Run MCP tool server on http://localhost:8001"
	@echo "  make run       Run FastAPI, Streamlit UI, and MCP together"

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .

api:
	$(PYTHON) run.py api

ui:
	$(PYTHON) run.py ui

mcp:
	$(PYTHON) run.py mcp

run:
	$(PYTHON) run.py all
