from pathlib import Path
from datetime import datetime

from .analyzer_interface import LanguageAnalyzer
from ..models.analysis_result import AnalysisResult, AnalysisMeta
from ..models.method_node import ModuleNode
from ..ingestion.project_scanner import ScanConfig, scan_project
from .js_ast_visitor import JSASTVisitor
from .symbol_table import ProjectSymbolTable
from .js_call_resolver import JSCallResolver
from ..analysis.graph_builder import GraphBuilder
from ..metrics.basic_metrics import compute_basic_metrics
from ..metrics.graph_metrics import compute_graph_metrics

class JavaScriptAnalyzer(LanguageAnalyzer):
    def analyze(self, project_path: Path, project_slug: str, exclude_tests: bool = False, max_file_size_kb: int = 500, oscar_version: str = "0.1.0") -> AnalysisResult:
        from .dependency_extractor import extract_dependencies
        project_deps = extract_dependencies(project_path, "npm")
        
        # 1. Scan for files
        from app.ingestion.project_scanner import DEFAULT_EXCLUDE_DIRS, ScanConfig
        js_excludes = set(DEFAULT_EXCLUDE_DIRS) - {"build", "dist"}
        
        config = ScanConfig(
            root_path=project_path,
            exclude_tests=exclude_tests,
            max_file_size_kb=max_file_size_kb,
            exclude_dirs=js_excludes
        )
        source_files = scan_project(config)
        
        methods = []
        classes = []
        modules = []
        imports = []
        call_edges = []
        
        # 2. Extract AST per file
        for sf in source_files:
            modules.append(ModuleNode(
                id=sf.module_path,
                file_path=sf.relative_path,
                package=None
            ))
            
            visitor = JSASTVisitor(sf, project_path)
            visitor.extract()
            
            methods.extend(visitor.methods)
            classes.extend(visitor.classes)
            imports.extend(visitor.imports)
            call_edges.extend(visitor.call_edges)

        # 3. Build Symbol Table
        sym_table_builder = ProjectSymbolTable()
        sym_table = sym_table_builder.build(modules, imports, methods, classes)
        
        # 4. Resolve Calls
        resolver = JSCallResolver(methods, classes, modules, imports, sym_table, project_deps)
        resolved_calls = resolver.resolve(call_edges)
        
        resolved_count = sum(1 for c in resolved_calls if c.call_type not in ("unresolved", "external", "dynamic"))
        unresolved_count = sum(1 for c in resolved_calls if c.call_type == "unresolved")
        external_count = sum(1 for c in resolved_calls if c.call_type == "external")
        dynamic_count = sum(1 for c in resolved_calls if c.call_type == "dynamic")
        total_calls = len(resolved_calls)
        # Denominator: exclude both external (out-of-project) and dynamic (runtime-dispatched)
        internal_calls_denominator = total_calls - external_count - dynamic_count
        resolution_rate = (internal_calls_denominator - unresolved_count) / internal_calls_denominator if internal_calls_denominator > 0 else 1.0
        
        # 5. Build Graph and calculate metrics
        gb = GraphBuilder()
        graph = gb.build(methods, resolved_calls)
        
        metrics = compute_basic_metrics(graph, methods, resolved_calls)
        advanced_metrics = compute_graph_metrics(graph)
        
        for m in metrics:
            adv = advanced_metrics.get(m.method_id, {})
            m.betweenness_centrality = adv.get("betweenness_centrality")
            m.pagerank = adv.get("pagerank")
            m.community_id = adv.get("community_id")
            m.blast_radius = adv.get("blast_radius")
        
        meta = AnalysisMeta(
            project_slug=project_slug,
            project_path=str(project_path),
            analyzed_at=datetime.utcnow(),
            oscar_version=oscar_version,
            file_count=len(source_files),
            total_loc=sum(m.loc for m in methods),  # approximation
            method_count=len(methods),
            class_count=len(classes),
            module_count=len(modules),
            edge_count=resolved_count,
            unresolved_call_count=unresolved_count,
            analysis_approach="tree_sitter_static",
            resolution_rate=round(resolution_rate, 3)
        )
        
        return AnalysisResult(
            meta=meta,
            methods=methods,
            classes=classes,
            modules=modules,
            calls=resolved_calls,
            imports=imports,
            inheritance=[], # Simplified for now
            metrics=metrics
        )
