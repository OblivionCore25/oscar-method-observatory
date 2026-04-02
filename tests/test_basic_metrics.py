import networkx as nx
from app.metrics.basic_metrics import compute_basic_metrics
from app.models.method_node import MethodNode, MethodKind
from app.models.call_edge import CallEdge, CallType

def test_compute_basic_metrics():
    m1 = MethodNode(id="m1", name="m1", qualified_name="m1", kind=MethodKind.FUNCTION, file_path="f", line_start=1, line_end=2, module="m")
    m2 = MethodNode(id="main", name="main", qualified_name="main", kind=MethodKind.FUNCTION, file_path="f", line_start=3, line_end=4, module="m")
    
    c1 = CallEdge(source_id="main", target_id="m1", call_type=CallType.DIRECT, line=2, confidence=1.0)
    
    graph = nx.DiGraph()
    graph.add_edge("main", "m1")
    
    metrics = compute_basic_metrics(graph, [m1, m2], [c1])
    metrics_map = {m.method_id: m for m in metrics}
    
    assert metrics_map["main"].fan_out == 1
    assert metrics_map["main"].fan_in == 0
    assert not metrics_map["main"].is_orphan  # 'main' is an entry point
    
    assert metrics_map["m1"].fan_in == 1
    assert metrics_map["m1"].fan_out == 0
    assert metrics_map["m1"].is_leaf
