import collections
from typing import Set, List
from pydantic import BaseModel
from collections import defaultdict
from app.models.method_node import MethodNode, ClassNode, ModuleNode
from app.models.call_edge import CallEdge, ImportEdge
from app.models.analysis_result import AnalysisResult


class ReachabilityResult(BaseModel):
    function: str
    status: str  # "REACHABLE", "UNREACHABLE", "UNKNOWN"
    path: List[str] = []
    reason: str = ""


class ReachabilityAnalyzer:
    """
    Determines whether a target function is structurally reachable from
    any public API entry point via the resolved call graph.

    Uses export-aware entry point detection to avoid the false-positive
    problem of zero-fan-in heuristics.
    """

    def find_entry_points(
        self,
        methods: List[MethodNode],
        call_edges: List[CallEdge],
        modules: List[ModuleNode] = None,
        imports: List[ImportEdge] = None,
        classes: List[ClassNode] = None,
    ) -> Set[str]:
        """
        Identify public API entry points using a three-tier strategy:

        Tier 1 — Explicit Exports:
            Python: Names re-exported from __init__.py (via `from .mod import X`
            or listed in __all__).
            JavaScript: Functions defined in or re-exported from index.js.

        Tier 2 — Public Definitions in Entry Modules:
            Public functions/methods (non-underscore-prefixed) defined directly
            in __init__.py, index.js, main.py, or app.py.

        Tier 3 — Top-Level Public API (filtered heuristic):
            Public, non-private functions with zero internal callers that are
            defined in top-level library modules (not deeply nested utilities).
            Excludes: __dunder__ methods, _private functions, anonymous_* functions.
        """
        entry_points = set()
        modules = modules or []
        imports = imports or []
        classes = classes or []

        # Build helper indexes
        method_by_id = {m.id: m for m in methods}
        methods_by_name: dict[str, list[MethodNode]] = {}
        for m in methods:
            methods_by_name.setdefault(m.name, []).append(m)
        class_by_name: dict[str, list[ClassNode]] = {}
        for c in (classes or []):
            class_by_name.setdefault(c.name, []).append(c)
        # Set of all known definition names for filtering
        all_defined_names = set(methods_by_name.keys()) | set(class_by_name.keys())

        # Package entry files (for Tier 1 export detection): only __init__.py / index.js
        package_entry_files = set()
        # Broader entry files (for Tier 2): includes main.py, app.py, cli.py
        entry_files = set()
        for mod in modules:
            fp = mod.file_path.lower()
            if any(fp.endswith(p) for p in (
                '__init__.py', 'index.js', 'index.ts', 'index.mjs',
            )):
                package_entry_files.add(mod.file_path)
                entry_files.add(mod.file_path)
            elif any(fp.endswith(p) for p in ('main.py', 'app.py', 'cli.py')):
                entry_files.add(mod.file_path)

        # ── Tier 1: Explicit re-exports from __init__.py / index.js ─────
        exported_names = set()

        # Build set of module IDs that correspond to package entry files
        entry_module_ids = set()
        for mod in modules:
            if mod.file_path in package_entry_files:
                entry_module_ids.add(mod.id)

        for imp in imports:
            # If this import originates from an entry module (__init__.py, index.js, etc.)
            # then the imported names are part of the public API — but only if they
            # resolve to definitions within this project (not external re-imports).
            if imp.source_module in entry_module_ids:
                for name in imp.imported_names:
                    if name != "*" and not name.startswith('_'):
                        # Only include names that have definitions in the project
                        if name in all_defined_names:
                            exported_names.add(name)

        # Match exported names to actual definitions
        for name in exported_names:
            # Match as standalone function (not a class method)
            for m in methods_by_name.get(name, []):
                if m.class_name is None:  # Top-level function only
                    entry_points.add(m.id)
            # Match as class → public methods are entry points.
            # Any consumer can call any public method on an exported class
            # (e.g., app.run(), app.route(), blueprint.register()).
            # Private methods (_prefixed) are NOT entry points — they are
            # internal implementation details reachable only via public methods.
            for c in class_by_name.get(name, []):
                for mid in c.method_ids:
                    m = method_by_id.get(mid)
                    if m and not m.name.startswith('_'):
                        entry_points.add(m.id)
                # Constructor is always an entry point
                for m in methods:
                    if m.class_name == name and m.name in ('__init__', 'constructor'):
                        entry_points.add(m.id)

        # ── Tier 2: Public standalone functions in entry files ───────────
        for method in methods:
            if method.file_path in entry_files:
                # Only standalone functions, not class methods
                if method.class_name is None and not method.name.startswith('_'):
                    entry_points.add(method.id)

        # ── Tier 3: Filtered zero-fan-in heuristic ──────────────────────
        # Only if Tiers 1+2 found fewer than 3 entry points (e.g., for
        # packages without __init__.py or index.js, like single-file libs)
        if len(entry_points) < 3:
            project_ids = {m.id for m in methods}
            fan_in = defaultdict(int)
            for edge in call_edges:
                if edge.target_id in project_ids and edge.call_type not in ('external', 'dynamic'):
                    fan_in[edge.target_id] += 1

            for method in methods:
                if fan_in[method.id] == 0:
                    name = method.name
                    # Exclude private, dunder, and anonymous methods
                    if name.startswith('_') and not name.startswith('__'):
                        continue
                    if name.startswith('__') and name.endswith('__') and name != '__init__':
                        continue
                    if name.startswith('anonymous'):
                        continue
                    # Only top-level functions in non-nested modules
                    if method.class_name is None:
                        entry_points.add(method.id)

        return entry_points

    def check_reachability(
        self,
        target_function_names: List[str],
        analysis_result: AnalysisResult,
    ) -> List[ReachabilityResult]:
        """
        For each target function name:
        1. Find matching method node(s) by name
        2. Trace backward from vulnerable function to any entry point
        3. Determine REACHABLE / UNREACHABLE / UNKNOWN statuses
        """
        methods = analysis_result.methods
        call_edges = analysis_result.calls
        resolution_rate = analysis_result.meta.resolution_rate

        entry_points = self.find_entry_points(
            methods,
            call_edges,
            modules=getattr(analysis_result, 'modules', None),
            imports=getattr(analysis_result, 'imports', None),
            classes=getattr(analysis_result, 'classes', None),
        )

        # Build inverse graph (target -> list of sources) to traverse backwards
        project_ids = {m.id for m in methods}
        inverse_graph = defaultdict(list)
        for edge in call_edges:
            if edge.source_id in project_ids and edge.target_id in project_ids:
                inverse_graph[edge.target_id].append(edge.source_id)

        results = []
        for target_func in target_function_names:
            target_func = target_func.strip()
            if not target_func:
                continue

            # Allow substring match because names might be fully qualified
            matching_methods = [
                m.id for m in methods
                if m.name == target_func or m.name.endswith(f".{target_func}")
            ]

            if not matching_methods:
                results.append(ReachabilityResult(
                    function=target_func,
                    status="UNKNOWN",
                    reason="No matching method found in AST codebase."
                ))
                continue

            # BFS backwards from any of the matching methods
            found_path = None

            for start_node in matching_methods:
                queue = collections.deque([(start_node, [start_node])])
                visited = {start_node}

                while queue and not found_path:
                    curr, path = queue.popleft()

                    if curr in entry_points:
                        found_path = path[::-1]  # Reverse: entry_point -> ... -> target
                        break

                    for neighbor in inverse_graph[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append((neighbor, path + [neighbor]))

                if found_path:
                    break

            if found_path:
                results.append(ReachabilityResult(
                    function=target_func,
                    status="REACHABLE",
                    path=found_path,
                    reason="Reachable from a public entry point."
                ))
            else:
                if resolution_rate < 0.85:
                    results.append(ReachabilityResult(
                        function=target_func,
                        status="UNKNOWN",
                        reason=f"Unreachable but low AST resolution rate ({resolution_rate*100:.1f}%). High chance of dynamic ambiguity."
                    ))
                else:
                    results.append(ReachabilityResult(
                        function=target_func,
                        status="UNREACHABLE",
                        reason=f"High-confidence unreachable (resolution rate {resolution_rate*100:.1f}%). Mathematically isolated."
                    ))

        return results
