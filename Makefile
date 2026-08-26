PYTHON ?= python3
export PYTHONPATH := src
COMPOSE ?= docker compose

.PHONY: help install api ui mcp run docker-build docker-up docker-down docker-logs

help:
	@echo "Banking Agent commands"
	@echo "  make install       Install Python dependencies"
	@echo "  make api           Run FastAPI on http://localhost:8000"
	@echo "  make ui            Run Streamlit UI on http://localhost:8501"
	@echo "  make mcp           Run MCP tool server on http://localhost:8001"
	@echo "  make run           Run FastAPI, Streamlit UI, and MCP together"
	@echo "  make docker-build  Build the Docker image"
	@echo "  make docker-up     Start api, ui, and mcp with Docker Compose"
	@echo "  make docker-down   Stop Docker Compose services"
	@echo "  make docker-logs   Follow Docker Compose logs"

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

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up --build

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f
