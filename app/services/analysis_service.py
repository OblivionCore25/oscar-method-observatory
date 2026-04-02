import ast
from datetime import datetime, timezone
from pathlib import Path
from ..ingestion.project_scanner import ScanConfig, scan_project
from ..ingestion.source_reader import read_and_parse
from ..analysis.ast_visitor import ASTVisitor
from ..analysis.call_resolver import CallResolver
from ..analysis.graph_builder import GraphBuilder
from ..metrics.basic_metrics import compute_basic_metrics
from ..models.analysis_result import AnalysisResult, AnalysisMeta
from ..storage.sqlite_storage import SqliteStorage


class AnalysisService:

    def __init__(self, data_directory: Path, oscar_version: str = "0.1.0", max_file_size_kb: int = 500):
        self.data_directory = data_directory
        self.oscar_version = oscar_version
        self.max_file_size_kb = max_file_size_kb
        self.storage = SqliteStorage(data_directory)

    def analyze(self, project_path: str, project_slug: str, exclude_tests: bool = False) -> AnalysisResult:
        """
        Full pipeline: scan → parse → extract → resolve → metrics → store → return.
        """
        root = Path(project_path).resolve()

        # ── 1. Scan ──────────────────────────────────────────────────
        config = ScanConfig(root_path=root, exclude_tests=exclude_tests, max_file_size_kb=self.max_file_size_kb)
        source_files = scan_project(config)

        # ── 2. Parse all files ───────────────────────────────────────
        parsed_sources = [read_and_parse(f) for f in source_files]

        # ── 3. Extract entities file-by-file ─────────────────────────
        all_methods, all_classes, all_modules = [], [], []
        all_raw_calls, all_imports, all_inheritance = [], [], []
        import_map: dict[str, dict[str, str]] = {}  # module_id → {local → resolved}

        for parsed in parsed_sources:
            if parsed.ast_tree is None:
                continue  # skip unparseable files
            visitor = ASTVisitor(
                module_id=parsed.source_file.module_path,
                file_path=parsed.source_file.relative_path,
                relative_path=parsed.source_file.relative_path,
            )
            result = visitor.extract(parsed.ast_tree)

            all_methods.extend(result.methods)
            all_classes.extend(result.classes)
            all_modules.append(result.module)
            all_raw_calls.extend(result.raw_calls)
            all_imports.extend(result.imports)
            all_inheritance.extend(result.inheritance)

            # Delete old import map logic. We now use the global symbol table.

        # ── 3.5 Build Project-Wide Symbol Table ──────────────────────
        from ..analysis.symbol_table import ProjectSymbolTable
        symbol_table_builder = ProjectSymbolTable()
        global_symbol_table = symbol_table_builder.build(
            modules=all_modules,
            imports=all_imports,
            methods=all_methods,
            classes=all_classes
        )

        # ── 4. Resolve calls ─────────────────────────────────────────
        resolver = CallResolver(
            all_methods=all_methods,
            all_classes=all_classes,
            import_map=global_symbol_table,
        )
        resolved_calls = [resolver.resolve(rc) for rc in all_raw_calls]
        resolved_calls = [c for c in resolved_calls if c is not None]

        # ── 5. Build graph ───────────────────────────────────────────
        graph_builder = GraphBuilder()
        graph = graph_builder.build(all_methods, resolved_calls)

        # ── 6. Compute metrics ───────────────────────────────────────
        metrics = compute_basic_metrics(graph, all_methods, resolved_calls)

        from ..metrics.graph_metrics import compute_graph_metrics
        advanced_metrics = compute_graph_metrics(graph)
        
        for m in metrics:
            adv = advanced_metrics.get(m.method_id, {})
            m.betweenness_centrality = adv.get("betweenness_centrality")
            m.pagerank = adv.get("pagerank")
            m.community_id = adv.get("community_id")
            m.blast_radius = adv.get("blast_radius")

        # ── 7. Compute analysis metadata ─────────────────────────────
        unresolved_count = sum(1 for c in resolved_calls if c.call_type == "unresolved")
        total_calls = len(resolved_calls)
        resolution_rate = (
            (total_calls - unresolved_count) / total_calls if total_calls > 0 else 1.0
        )
        total_loc = sum(f.size_bytes for f in source_files) // 50  # rough estimate

        meta = AnalysisMeta(
            project_slug=project_slug,
            project_path=str(root),
            analyzed_at=datetime.now(timezone.utc),
            oscar_version=self.oscar_version,
            file_count=len(parsed_sources),
            total_loc=total_loc,
            method_count=len(all_methods),
            class_count=len(all_classes),
            module_count=len(all_modules),
            edge_count=sum(1 for c in resolved_calls if not c.target_id.startswith("unresolved:")),
            unresolved_call_count=unresolved_count,
            resolution_rate=round(resolution_rate, 4),
        )

        # ── 8. Assemble result ───────────────────────────────────────
        result = AnalysisResult(
            meta=meta,
            methods=all_methods,
            classes=all_classes,
            modules=all_modules,
            calls=resolved_calls,
            imports=all_imports,
            inheritance=all_inheritance,
            metrics=metrics,
        )

        # ── 9. Persist ───────────────────────────────────────────────
        self.storage.save(project_slug, result)

        return result

    def load(self, project_slug: str) -> AnalysisResult | None:
        return self.storage.load(project_slug)

    def list_projects(self) -> list[str]:
        return self.storage.list_projects()
