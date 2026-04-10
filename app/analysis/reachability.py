import collections
from typing import Set, List
from pydantic import BaseModel
from collections import defaultdict
from app.models.method_node import MethodNode
from app.models.call_edge import CallEdge
from app.models.analysis_result import AnalysisResult

class ReachabilityResult(BaseModel):
    function: str
    status: str  # "REACHABLE", "UNREACHABLE", "UNKNOWN"
    path: List[str] = []
    reason: str = ""

class ReachabilityAnalyzer:
    def find_entry_points(self, methods: List[MethodNode], call_edges: List[CallEdge]) -> Set[str]:
        """
        Identify public API entry points:
        - Functions in __init__.py / index.js / main.py 
        - Functions with 0 internal callers (potential entry points)
        """
        entry_points = set()
        
        # Calculate fan-in for all nodes
        fan_in = defaultdict(int)
        for edge in call_edges:
            fan_in[edge.target_id] += 1
            
        for method in methods:
            file_path = method.file_path.lower()
            if "index.js" in file_path or "index.ts" in file_path or "__init__.py" in file_path or "main.py" in file_path:
                entry_points.add(method.id)
            elif fan_in[method.id] == 0:
                entry_points.add(method.id)
                
        return entry_points

    def check_reachability(self, 
                           target_function_names: List[str], 
                           analysis_result: AnalysisResult) -> List[ReachabilityResult]:
        """
        For each target function name:
        1. Find matching method node(s) by name
        2. Trace backward from vulnerable function to any entry point 
        3. Determine REACHABLE / UNREACHABLE / UNKNOWN statuses
        """
        methods = analysis_result.methods
        call_edges = analysis_result.calls
        resolution_rate = analysis_result.meta.resolution_rate
        
        entry_points = self.find_entry_points(methods, call_edges)
        
        # Build inverse graph (target -> list of sources) to traverse backwards
        inverse_graph = defaultdict(list)
        for edge in call_edges:
            inverse_graph[edge.target_id].append(edge.source_id)

        results = []
        for target_func in target_function_names:
            target_func = target_func.strip()
            if not target_func:
                continue
                
            # Allow substring match because names might be fully qualified
            matching_methods = [m.id for m in methods if m.name == target_func or m.name.endswith(f".{target_func}")]
            
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
                visited = set([start_node])
                
                while queue and not found_path:
                    curr, path = queue.popleft()
                    
                    if curr in entry_points:
                        found_path = path[::-1] # Reverse the path so it reads entry_point -> ... -> target
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
