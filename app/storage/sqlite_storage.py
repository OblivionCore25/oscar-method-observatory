from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from ..models.analysis_result import AnalysisResult, AnalysisMeta, MethodMetrics
from ..models.method_node import MethodNode, ClassNode, ModuleNode, MethodKind
from ..models.call_edge import CallEdge, ImportEdge, InheritanceEdge, CallType
from ..models.git_profile import GitRepoHealth, GitFileChurn, GitAnalysisResult

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

    def list_projects(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT project_slug, meta_json FROM analysis_runs GROUP BY project_slug")
            
            results = []
            for row in cur.fetchall():
                meta = json.loads(row["meta_json"])
                if meta.get("method_count", 0) == 0:
                    continue
                ecosystem = "npm" if meta.get("analysis_approach") == "tree_sitter_static" else "pypi"
                results.append({"slug": row["project_slug"], "ecosystem": ecosystem})
            return results

    def save_git_profile(self, result: GitAnalysisResult) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            
            cur.execute("DELETE FROM git_repo_profiles WHERE project_slug = ?", (result.health.project_slug,))
            cur.execute("DELETE FROM git_file_churn WHERE project_slug = ?", (result.health.project_slug,))
            
            h = result.health
            cur.execute(
                """INSERT INTO git_repo_profiles (
                    project_slug, repo_url, analyzed_at, total_commits, total_contributors,
                    active_contributors_90d, bus_factor, first_commit_date, last_commit_date,
                    days_since_last_commit, analysis_window_days, commits_in_window,
                    monthly_commit_series, top_contributors_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    h.project_slug, h.repo_url, h.analyzed_at.isoformat(), h.total_commits,
                    h.total_contributors, h.active_contributors_90d, h.bus_factor,
                    h.first_commit_date, h.last_commit_date, h.days_since_last_commit,
                    h.analysis_window_days, h.commits_in_window,
                    json.dumps(h.monthly_commit_series), json.dumps(h.top_contributors)
                )
            )
            profile_id = cur.lastrowid
            
            churn_data = []
            for c in result.files:
                churn_data.append((
                    profile_id, h.project_slug, c.file_path, c.commits,
                    c.author_count, c.last_modified, json.dumps(c.top_authors)
                ))
                
            cur.executemany(
                """INSERT INTO git_file_churn (
                    profile_id, project_slug, file_path, commits, author_count,
                    last_modified, top_authors_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                churn_data
            )

    def load_git_profile(self, project_slug: str) -> GitRepoHealth | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM git_repo_profiles WHERE project_slug = ?", (project_slug,))
            row = cur.fetchone()
            if not row:
                return None
            
            from datetime import datetime
            
            return GitRepoHealth(
                project_slug=row["project_slug"],
                repo_url=row["repo_url"],
                analyzed_at=datetime.fromisoformat(row["analyzed_at"]),
                total_commits=row["total_commits"],
                total_contributors=row["total_contributors"],
                active_contributors_90d=row["active_contributors_90d"],
                bus_factor=row["bus_factor"],
                first_commit_date=row["first_commit_date"],
                last_commit_date=row["last_commit_date"],
                days_since_last_commit=row["days_since_last_commit"],
                analysis_window_days=row["analysis_window_days"],
                commits_in_window=row["commits_in_window"],
                monthly_commit_series=json.loads(row["monthly_commit_series"] or "[]"),
                top_contributors=json.loads(row["top_contributors_json"] or "[]")
            )

    def load_git_file_churn(self, project_slug: str) -> list[GitFileChurn]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM git_file_churn WHERE project_slug = ?", (project_slug,))
            rows = cur.fetchall()
            
            results = []
            for row in rows:
                results.append(GitFileChurn(
                    file_path=row["file_path"],
                    commits=row["commits"],
                    author_count=row["author_count"],
                    last_modified=row["last_modified"],
                    top_authors=json.loads(row["top_authors_json"] or "[]")
                ))
            return results

    def load_git_file_churn_map(self, project_slug: str) -> dict[str, GitFileChurn]:
        churns = self.load_git_file_churn(project_slug)
        return {c.file_path: c for c in churns}
