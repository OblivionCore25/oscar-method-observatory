from app.analysis.call_resolver import CallResolver
from app.models.method_node import MethodNode, MethodKind
from app.models.call_edge import CallType

def test_resolve_direct_call():
    m1 = MethodNode(id="mod:m1", name="m1", qualified_name="m1", kind=MethodKind.FUNCTION, file_path="f", line_start=1, line_end=2, module="mod")
    
    resolver = CallResolver(all_methods=[m1], all_classes=[], import_map={})
    raw_call = {
        "caller_id": "mod:caller",
        "call_expr_type": "name",
        "call_name": "m1",
        "attr_name": None,
        "receiver_name": None,
        "line": 5,
        "argument_count": 0,
        "is_conditional": False
    }
    
    resolved = resolver.resolve(raw_call)
    assert resolved is not None
    assert resolved.target_id == "mod:m1"
    assert resolved.call_type == CallType.DIRECT
