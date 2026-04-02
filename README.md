# OSCAR — Method Level Observatory

This repository is a core backend module of the broader **OSCAR** project:
> **OSCAR — Open Supply-Chain Assurance & Resilience for Cloud-Native Software Ecosystems**

## 🌐 The OSCAR Architecture

The OSCAR ecosystem is decoupled into three standalone repositories that work together to form a comprehensive supply-chain and risk intelligence platform:

1. **`oscar-dependency-observatory`:** Analyzes macro-level transitive dependencies between packages (e.g., npm and PyPI) across entire software ecosystems.
2. **`oscar-method-observatory` (This Repository):** Analyzes micro-level, internal source code topologies, resolving deep function-to-function abstract syntax trees and structural risks.
3. **`oscar-frontend`:** The unified React/Vite UI that bridges both backends into an interactive dashboard, visualizer, and method explorer.

---

## 📌 Overview

The **Method Level Observatory** focuses on deep code-level topological maps. Rather than asking "Which package brings in Log4j?", it answers infrastructural questions about the inside of a single package:

- By parsing Abstract Syntax Trees (**AST**), we can graph internal methods and the exact resolution of their function calls.
- Calculates micro-metrics like Betweenness Centrality, Louvain communities, PageRank, and Blast Radius limitations.
- Ranks architectural "Hotspots" within codebases that have a high structural risk to break independent components if modified or compromised.

---

## 🗂️ Project Structure

This project operates as a Python FastAPI application paired with an embedded SQLite persistence layer.

```
oscar-method-observatory/
├── app/
│   ├── analysis/           # AST traversal, symbolic extraction, Call graph resolvers
│   ├── api/                # FastAPI routes (ingestion POSTs, graph queries)
│   ├── config.py           # Configuration schema setup
│   ├── ingestion/          # Project crawlers / script downloaders
│   ├── main.py             # FastAPI entry point
│   ├── metrics/            # Computes Louvain communities and PageRank topologies
│   ├── models/             # Models and SQLite table mappers
│   ├── services/           # Controller logic
│   └── storage/            # Relational SQLite bindings
├── data/                   # The generated method_graph.db SQLite database
├── tests/                  # Pytest functionality assurance
└── requirements.txt        # Production dependencies
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Virtual Environment

### Start the Backend Server

```bash
# 1. Initialize your python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install requirements
pip install -r requirements.txt

# 3. Start the FastAPI Uvicorn Server (Note: Port 8001 is standard for this backend)
uvicorn app.main:app --port 8001 --reload
```

The server will start on `http://localhost:8001`.
You can view interactive interactive documentation at `http://localhost:8001/docs`.

### Using the Observatory

Since this is an offline analyzer, its database starts **empty**. To visualize code on the `oscar-frontend`, you first need to parse a local repository:

```bash
# Trigger an analysis job for a project on your filesystem
curl -X POST "http://localhost:8001/methods/analyze" \
     -H "Content-Type: application/json" \
     -d '{
           "project_path": "/absolute/path/to/some/python/project",
           "project_slug": "project_name"
         }'
```
