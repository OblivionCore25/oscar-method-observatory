import sqlite3
import json
from pathlib import Path
from ..models.analysis_result import AnalysisResult, AnalysisMeta, MethodMetrics
from ..models.method_node import MethodNode, ClassNode, ModuleNode, MethodKind
from ..models.call_edge import CallEdge, ImportEdge, InheritanceEdge, CallType

class SqliteStorage:
    """
    Relational SQLite storage engine replacing JSON flat-files for the Method Observatory.
    """

    def __init__(self, data_directory: Path):
        self.root = data_directory / "method_observatory"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "method_graph.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
            -- Analysis records
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_slug TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                meta_json TEXT NOT NULL
            );
            
            -- Method entities
            CREATE TABLE IF NOT EXISTS methods (
                id TEXT,
                run_id INTEGER,
                project_slug TEXT,
                name TEXT,
                module TEXT,
                class_name TEXT,
                complexity INTEGER,
                loc INTEGER,
                json_data TEXT,
                PRIMARY KEY (run_id, id)
            );
            
            -- Call edges
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                project_slug TEXT,
                source_id TEXT,
                target_id TEXT,
                call_type TEXT,
                confidence REAL,
                json_data TEXT
            );
            
            -- Metrics
            CREATE TABLE IF NOT EXISTS method_metrics (
                method_id TEXT,
                run_id INTEGER,
                project_slug TEXT,
                bottleneck_score REAL,
                betweenness_centrality REAL,
                pagerank REAL,
                community_id INTEGER,
                blast_radius INTEGER,
                json_data TEXT,
                PRIMARY KEY (run_id, method_id)
            );

            -- Auxiliary blobs for reconstructability
            CREATE TABLE IF NOT EXISTS auxiliary_data (
                run_id INTEGER,
                project_slug TEXT,
                class_json TEXT,
                module_json TEXT,
                import_json TEXT,
                inheritance_json TEXT,
                PRIMARY KEY (run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_methods_run ON methods(run_id);
            CREATE INDEX IF NOT EXISTS idx_calls_src ON calls(run_id, source_id);
            CREATE INDEX IF NOT EXISTS idx_calls_tgt ON calls(run_id, target_id);
            CREATE INDEX IF NOT EXISTS idx_metrics_run ON method_metrics(run_id);
            """)

    def save(self, project_slug: str, result: AnalysisResult) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            
            # 1. Clear out older runs for the same project immediately 
            # (Phase 2 focuses on singular offline DBs matching the flat-file pattern)
            cur.execute("DELETE FROM analysis_runs WHERE project_slug = ?", (project_slug,))
            cur.execute("DELETE FROM methods WHERE project_slug = ?", (project_slug,))
            cur.execute("DELETE FROM calls WHERE project_slug = ?", (project_slug,))
            cur.execute("DELETE FROM method_metrics WHERE project_slug = ?", (project_slug,))
            cur.execute("DELETE FROM auxiliary_data WHERE project_slug = ?", (project_slug,))

            # 2. Insert run header
            cur.execute(
                "INSERT INTO analysis_runs (project_slug, analyzed_at, meta_json) VALUES (?, ?, ?)",
                (project_slug, result.meta.analyzed_at.isoformat(), result.meta.model_dump_json())
            )
            run_id = cur.lastrowid

            # 3. Insert methods
            methods_data = []
            for m in result.methods:
                methods_data.append((
                    m.id, run_id, project_slug, m.name, m.module, m.class_name, m.complexity, m.loc, m.model_dump_json()
                ))
            cur.executemany(
                "INSERT OR IGNORE INTO methods (id, run_id, project_slug, name, module, class_name, complexity, loc, json_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                methods_data
            )

            # 4. Insert calls
            calls_data = []
            for c in result.calls:
                calls_data.append((
                    run_id, project_slug, c.source_id, c.target_id, c.call_type, c.confidence, c.model_dump_json()
                ))
            cur.executemany(
                "INSERT INTO calls (run_id, project_slug, source_id, target_id, call_type, confidence, json_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
                calls_data
            )

            # 5. Insert metrics
            metrics_data = []
            for mx in result.metrics:
                metrics_data.append((
                    mx.method_id, run_id, project_slug, mx.bottleneck_score, mx.betweenness_centrality, mx.pagerank, mx.community_id, mx.blast_radius, mx.model_dump_json()
                ))
            cur.executemany(
                "INSERT OR IGNORE INTO method_metrics (method_id, run_id, project_slug, bottleneck_score, betweenness_centrality, pagerank, community_id, blast_radius, json_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                metrics_data
            )

            # 6. Insert auxiliary reconstructive JSON data
            cur.execute(
                "INSERT INTO auxiliary_data (run_id, project_slug, class_json, module_json, import_json, inheritance_json) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id, project_slug,
                    json.dumps([c.model_dump(mode="json") for c in result.classes]),
                    json.dumps([m.model_dump(mode="json") for m in result.modules]),
                    json.dumps([i.model_dump(mode="json") for i in result.imports]),
                    json.dumps([i.model_dump(mode="json") for i in result.inheritance]),
                )
            )

    def load(self, project_slug: str) -> AnalysisResult | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            cur.execute("SELECT id, meta_json FROM analysis_runs WHERE project_slug = ? ORDER BY id DESC LIMIT 1", (project_slug,))
            run_row = cur.fetchone()
            if not run_row:
                return None
            
            run_id = run_row["id"]
            meta_data = json.loads(run_row["meta_json"])
            meta = AnalysisMeta(**meta_data)
            
            cur.execute("SELECT json_data FROM methods WHERE run_id = ?", (run_id,))
            methods = [MethodNode(**json.loads(row["json_data"])) for row in cur.fetchall()]

            cur.execute("SELECT json_data FROM calls WHERE run_id = ?", (run_id,))
            calls = [CallEdge(**json.loads(row["json_data"])) for row in cur.fetchall()]

            cur.execute("SELECT json_data FROM method_metrics WHERE run_id = ?", (run_id,))
            metrics = [MethodMetrics(**json.loads(row["json_data"])) for row in cur.fetchall()]

            cur.execute("SELECT * FROM auxiliary_data WHERE run_id = ?", (run_id,))
            aux_row = cur.fetchone()
            if not aux_row:
                return None

            classes = [ClassNode(**c) for c in json.loads(aux_row["class_json"])]
            modules = [ModuleNode(**m) for m in json.loads(aux_row["module_json"])]
            imports = [ImportEdge(**i) for i in json.loads(aux_row["import_json"])]
            inheritance = [InheritanceEdge(**i) for i in json.loads(aux_row["inheritance_json"])]

            return AnalysisResult(
                meta=meta,
                methods=methods,
                classes=classes,
                modules=modules,
                calls=calls,
                imports=imports,
                inheritance=inheritance,
                metrics=metrics
            )

    def list_projects(self) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT project_slug FROM analysis_runs")
            return [row[0] for row in cur.fetchall()]
