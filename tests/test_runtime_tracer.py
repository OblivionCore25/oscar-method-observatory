import time
import networkx as nx
from pathlib import Path
from app.analysis.runtime_tracer import RuntimeTracer
from app.models.method_node import MethodNode, MethodKind
from app.analysis.graph_builder import GraphBuilder

def simple_callee():
    return 42

def simple_caller():
    for _ in range(3):
        simple_callee()
    return True

def test_runtime_tracer_basic_extraction():
    # Provide the root path matching this file exactly to prevent huge traces
    root = str(Path(__file__).parent.resolve())
    tracer = RuntimeTracer(project_root=root)
    
    tracer.start()
    simple_caller()
    records = tracer.stop()

    assert len(records) > 0
    
    # Verify accurate hit generation
    found_caller = False
    for r in records:
        if r.caller_name == "simple_caller" and r.callee_name == "simple_callee":
            assert r.count == 3
            found_caller = True
            
    assert found_caller

def test_merge_dynamic_traces_into_graph():
    root = str(Path(__file__).parent.resolve())
    tracer = RuntimeTracer(project_root=root)
    
    tracer.start()
    simple_caller()
    records = tracer.stop()
    
    # Craft MethodNodes directly referencing the functions Above
    methods = [
        MethodNode(
            id="mod:simple_caller", name="simple_caller", qualified_name="simple_caller",
            kind=MethodKind.FUNCTION, file_path="test_runtime_tracer.py",
            line_start=11, line_end=14, module="mod", loc=3, complexity=1
        ),
        MethodNode(
            id="mod:simple_callee", name="simple_callee", qualified_name="simple_callee",
            kind=MethodKind.FUNCTION, file_path="test_runtime_tracer.py",
            line_start=8, line_end=9, module="mod", loc=2, complexity=1
        )
    ]
    
    builder = GraphBuilder()
    G = nx.DiGraph()
    G.add_node("mod:simple_caller")
    G.add_node("mod:simple_callee")
    # Base connection setup with confidence 0.5 simulating Name_fallback
    G.add_edge("mod:simple_caller", "mod:simple_callee", **{"confidence": 0.5, "call_type": "name_match"})
    
    G_merged = builder.merge_dynamic_traces(G, records, methods)
    
    # Verification the OS tracer perfectly matched the path definitions and boosted the topology!
    edge_data = G_merged["mod:simple_caller"]["mod:simple_callee"]
    assert edge_data["confidence"] == 1.0
    assert edge_data["dynamic_hits"] == 3
