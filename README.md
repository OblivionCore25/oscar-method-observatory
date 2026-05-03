# OSCAR — Method Level Observatory

This repository is a core backend module of the broader **OSCAR** project:
> **OSCAR — Open Supply-Chain Assurance & Resilience for Cloud-Native Software Ecosystems**

## 🌐 The OSCAR Architecture

The OSCAR ecosystem is decoupled into three standalone repositories that work together to form a comprehensive supply-chain and risk intelligence platform:

1. **`oscar-dependency-observatory`:** Analyzes macro-level transitive dependencies between packages (npm and PyPI) across entire software ecosystems.
2. **`oscar-method-observatory` (This Repository):** Analyzes micro-level, internal source code topologies, resolving deep function-to-function abstract syntax trees and structural risks.
3. **`oscar-frontend`:** The unified React/Vite UI that bridges both backends into an interactive dashboard, visualizer, and method explorer.

---

## 📌 Overview

The **Method Level Observatory** focuses on deep code-level topological maps. Rather than asking "Which package brings in Log4j?", it answers infrastructural questions about the inside of a single package:

- By parsing Abstract Syntax Trees (**AST**), we can graph internal methods and the exact resolution of their function calls.
- Supports **Python** packages (via Python's `ast` module) and **JavaScript/TypeScript** packages (via `tree-sitter`).
- Calculates micro-metrics like Cyclomatic Complexity, Betweenness Centrality, Louvain communities, PageRank, and Blast Radius.
- Ranks architectural "Hotspots" within codebases using a composite risk score: `Complexity × Centrality × Blast Radius`.

---

## 🎯 Core Metrics

| Metric | What It Measures |
|---|---|
| **Cyclomatic Complexity** | Number of independent execution paths through a function |
| **Betweenness Centrality** | How often a method sits on the shortest path between other methods |
| **PageRank** | Recursive importance propagation through the internal call graph |
| **Blast Radius** | Total downstream methods affected if this function changes or fails |
| **Composite Risk** | `Complexity × Centrality × Blast Radius` — structural fragility index |
| **Community ID** | Louvain cluster assignment revealing tightly-coupled architectural modules |

---

## 🗂️ Project Structure

This project operates as a Python FastAPI application paired with an embedded SQLite persistence layer.

```
oscar-method-observatory/
├── app/
│   ├── analysis/           # AST traversal, symbolic extraction, call graph resolvers
│   │   ├── ast_visitor.py          # Python AST visitor (stdlib ast module)
│   │   ├── js_ast_visitor.py       # JavaScript/TypeScript AST visitor (tree-sitter)
│   │   ├── javascript_analyzer.py  # JS/TS analysis pipeline orchestrator
│   │   └── python_analyzer.py      # Python analysis pipeline orchestrator
│   ├── api/                # FastAPI routes (ingestion, graph queries, hotspots)
│   ├── config.py           # Configuration schema setup
│   ├── ingestion/          # Project scanners, PyPI and npm downloaders
│   │   ├── project_scanner.py      # File discovery and filtering
│   │   ├── pypi_downloader.py      # PyPI sdist/wheel fetcher & extractor
│   │   └── npm_downloader.py       # npm tarball fetcher & extractor
│   ├── main.py             # FastAPI entry point
│   ├── metrics/            # Computes Louvain communities, PageRank, and centrality
│   ├── models/             # Pydantic domain models (MethodNode, CallEdge, etc.)
│   ├── services/           # Analysis service controller logic
│   └── storage/            # SQLite and PostgreSQL storage backends
├── data/                   # The generated method_graph.db SQLite database
├── tests/                  # Pytest test suites
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
You can view interactive documentation at `http://localhost:8001/docs`.

### Using the Observatory

Since this is an offline analyzer, its database starts **empty**. You can populate it in two ways:

#### Auto-Ingest from Package Registry

Download and analyze a package directly from PyPI or npm:

```bash
# Analyze a PyPI package
curl -X POST "http://localhost:8001/methods/ingest/pypi/flask"

# Analyze an npm package (scoped packages use URL encoding)
curl -X POST "http://localhost:8001/methods/ingest/npm/%40babel%2Fcore"
```

#### Analyze a Local Project

Parse a project already on your filesystem:

```bash
curl -X POST "http://localhost:8001/methods/analyze" \
     -H "Content-Type: application/json" \
     -d '{
           "project_path": "/absolute/path/to/some/project",
           "project_slug": "project_name"
         }'
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
