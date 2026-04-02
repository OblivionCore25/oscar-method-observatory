import networkx as nx
from ..models.analysis_result import MethodMetrics
from ..models.method_node import MethodNode


# Methods matching these names are treated as "entry points" (not orphans)
ENTRY_POINT_NAMES = {
    "main", "__main__", "__init__", "__new__", "__call__",
    "__enter__", "__exit__", "__iter__", "__next__",
    # FastAPI/Flask route handlers will be detected by decorator in Phase 2
}


def compute_basic_metrics(
    graph: nx.DiGraph,
    methods: list[MethodNode],
    all_calls_including_external: list,  # includes unresolved calls per method
) -> list[MethodMetrics]:
    """
    Compute fan-in, fan-out, bottleneck score, leaf, and orphan flags
    for every method node in the graph.
    """
    # Count external calls per method (calls that left the project boundary)
    external_count: dict[str, int] = {}
    for call in all_calls_including_external:
        if call.target_id.startswith("unresolved:") or call.call_type == "unresolved":
            external_count[call.source_id] = external_count.get(call.source_id, 0) + 1

    results = []
    for method in methods:
        node_id = method.id

        if node_id not in graph:
            # Method exists but has no edges (neither caller nor callee found in project)
            results.append(MethodMetrics(
                method_id=node_id,
                fan_in=0, fan_out=0,
                fan_out_external=external_count.get(node_id, 0),
                bottleneck_score=0.0,
                is_leaf=True,
                is_orphan=method.name not in ENTRY_POINT_NAMES,
                complexity=method.complexity,
                loc=method.loc,
            ))
            continue

        fan_in = graph.in_degree(node_id)
        fan_out = graph.out_degree(node_id)
        fan_out_external = external_count.get(node_id, 0)

        # Bottleneck score: mirrors OSCAR's formula
        if fan_out > 0:
            bottleneck_score = float(fan_in * fan_out)
        else:
            bottleneck_score = float(fan_in)

        is_leaf = (fan_out == 0 and fan_out_external == 0)
        is_orphan = (fan_in == 0 and method.name not in ENTRY_POINT_NAMES)

        results.append(MethodMetrics(
            method_id=node_id,
            fan_in=fan_in,
            fan_out=fan_out,
            fan_out_external=fan_out_external,
            bottleneck_score=bottleneck_score,
            is_leaf=is_leaf,
            is_orphan=is_orphan,
            complexity=method.complexity,
            loc=method.loc,
        ))

    return results
