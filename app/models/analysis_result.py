from datetime import datetime
from pydantic import BaseModel
from .method_node import MethodNode, ClassNode, ModuleNode
from .call_edge import CallEdge, ImportEdge, InheritanceEdge


class MethodMetrics(BaseModel):
    method_id: str
    fan_in: int = 0                # Callers within project
    fan_out: int = 0               # Callees within project
    fan_out_external: int = 0      # Calls to external code
    bottleneck_score: float = 0.0  # fan_in × fan_out (or fan_in if fan_out=0)
    is_leaf: bool = False          # fan_out == 0
    is_orphan: bool = False        # fan_in == 0 and not an entry point
    complexity: int = 1
    loc: int = 0
    # Phase 2+ fields (None until computed)
    betweenness_centrality: float | None = None
    pagerank: float | None = None
    community_id: int | None = None
    blast_radius: int | None = None


class AnalysisMeta(BaseModel):
    project_slug: str
    project_path: str
    analyzed_at: datetime
    oscar_version: str = "0.1.0"
    file_count: int
    total_loc: int
    method_count: int
    class_count: int
    module_count: int
    edge_count: int
    unresolved_call_count: int
    analysis_approach: str = "ast_static"
    # Completeness estimate: resolved_calls / total_calls
    resolution_rate: float = 0.0


class AnalysisResult(BaseModel):
    meta: AnalysisMeta
    methods: list[MethodNode]
    classes: list[ClassNode]
    modules: list[ModuleNode]
    calls: list[CallEdge]
    imports: list[ImportEdge]
    inheritance: list[InheritanceEdge]
    metrics: list[MethodMetrics]
