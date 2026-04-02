import pytest
from pathlib import Path
from app.models.analysis_result import AnalysisResult, AnalysisMeta, MethodMetrics
from app.models.method_node import MethodNode, MethodKind
from app.models.call_edge import CallEdge, CallType
from app.storage.sqlite_storage import SqliteStorage
from datetime import datetime, timezone

def test_sqlite_storage_roundtrip(tmp_path: Path):
    storage = SqliteStorage(tmp_path)
    
    meta = AnalysisMeta(
        project_slug="test_project", project_path="/test", analyzed_at=datetime.now(timezone.utc),
        oscar_version="0.1.0", file_count=1, total_loc=10, method_count=1, class_count=0, module_count=0,
        edge_count=1, unresolved_call_count=0, resolution_rate=1.0
    )
    method = MethodNode(
        id="mod:func", name="func", qualified_name="func", kind=MethodKind.FUNCTION,
        file_path="mod.py", line_start=1, line_end=2, module="mod", loc=2, complexity=1
    )
    call = CallEdge(
        source_id="mod:func", target_id="mod:other", call_type=CallType.DIRECT,
        line=2, confidence=1.0, argument_count=0
    )
    metric = MethodMetrics(
        method_id="mod:func", fan_in=0, fan_out=1, fan_out_external=0,
        bottleneck_score=0.0, is_leaf=False, is_orphan=False, complexity=1, loc=2
    )
    
    result = AnalysisResult(
        meta=meta, methods=[method], classes=[], modules=[],
        calls=[call], imports=[], inheritance=[], metrics=[metric]
    )
    
    storage.save("test_project", result)
    
    loaded = storage.load("test_project")
    assert loaded is not None
    assert loaded.meta.project_slug == "test_project"
    assert len(loaded.methods) == 1
    assert loaded.methods[0].id == "mod:func"
    assert len(loaded.calls) == 1
    assert len(loaded.metrics) == 1
    assert loaded.metrics[0].method_id == "mod:func"
    assert "test_project" in storage.list_projects()
