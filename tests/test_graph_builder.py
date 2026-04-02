from app.analysis.graph_builder import GraphBuilder
from app.models.method_node import MethodNode, MethodKind
from app.models.call_edge import CallEdge, CallType

def test_graph_builder():
    m1 = MethodNode(id="m1", name="m1", qualified_name="m1", kind=MethodKind.FUNCTION, file_path="f", line_start=1, line_end=2, module="m")
    m2 = MethodNode(id="m2", name="m2", qualified_name="m2", kind=MethodKind.FUNCTION, file_path="f", line_start=3, line_end=4, module="m")
    
    c1 = CallEdge(source_id="m1", target_id="m2", call_type=CallType.DIRECT, line=2, confidence=1.0)
    
    builder = GraphBuilder()
    G = builder.build([m1, m2], [c1])
    
    assert G.number_of_nodes() == 2
    assert G.number_of_edges() == 1
    assert G.has_edge("m1", "m2")
    assert G["m1"]["m2"]["confidence"] == 1.0
