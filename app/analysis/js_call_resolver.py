from ..models.method_node import MethodNode, ClassNode, ModuleNode
from ..models.call_edge import CallEdge, CallType, ImportEdge
from .external_classifier import classify_call


class JSCallResolver:
    """
    Resolves abstract call sites extracted by JSASTVisitor into fully 
    qualified global identifiers based on JS heuristics (e.g. `this.`, `super.`).
    """
    def __init__(self, methods: list[MethodNode], classes: list[ClassNode], modules: list[ModuleNode], imports: list[ImportEdge], symbol_table: dict[str, dict[str, str]], project_dependencies: set[str] = None):
        # Build quick lookups against known IDs
        self.known_method_ids = {m.id for m in methods}
        self.classes_by_id = {c.id: c for c in classes}
        
        self.symbol_table = symbol_table
        self.project_dependencies = project_dependencies or set()
        
        # Build a reverse lookup for "name matching"
        # name -> list of possible method ids
        self.name_registry: dict[str, list[str]] = {}
        for m in methods:
            self.name_registry.setdefault(m.name, []).append(m.id)

    def resolve(self, edges: list[CallEdge]) -> list[CallEdge]:
        resolved: list[CallEdge] = []
        
        for edge in edges:
            call_text = edge.target_id
            source_parts = edge.source_id.split(":")
            source_module = source_parts[0]
            
            # 1. Self Calls: `this.method`
            if call_text.startswith("this."):
                method_name = call_text[5:]
                # We need the parent class ID
                if ":" in edge.source_id and "." in source_parts[1]:
                    class_name = source_parts[1].split(".")[0]
                    target_id = f"{source_module}:{class_name}.{method_name}"
                    
                    if target_id in self.known_method_ids:
                        edge.target_id = target_id
                        edge.call_type = CallType.SELF_CALL
                        edge.confidence = 0.85
                        resolved.append(edge)
                        continue
                        
            # 2. Super Calls: `super.method`
            if call_text.startswith("super."):
                method_name = call_text[6:]
                if ":" in edge.source_id and "." in source_parts[1]:
                    class_name = source_parts[1].split(".")[0]
                    cls = self.classes_by_id.get(f"{source_module}:{class_name}")
                    # If we mapped inheritance, we could look up the parent class definition
                    # Simplified for now: just map to the target ID format if parent known, else fallback to name match.
                    pass # Fallthrough to name matching for super
                    
            # 3. Simple function call (might be local, or imported)
            if "." not in call_text:
                # Check symbol table
                if source_module in self.symbol_table and call_text in self.symbol_table[source_module]:
                    edge.target_id = self.symbol_table[source_module][call_text]
                    edge.call_type = CallType.DIRECT
                    edge.confidence = 0.90
                    resolved.append(edge)
                    continue

                # Check if it refers to a local function within the same module
                local_fn_id = f"{source_module}:{call_text}"
                if local_fn_id in self.known_method_ids:
                    edge.target_id = local_fn_id
                    edge.call_type = CallType.DIRECT
                    edge.confidence = 0.85
                    resolved.append(edge)
                    continue
                    
            # 4. Method Calls on Objects: `obj.method` or `module.func`
            if "." in call_text:
                obj_name, method_name = call_text.split(".", 1)
                
                # Check if `obj_name` is an imported module
                if source_module in self.symbol_table and obj_name in self.symbol_table[source_module]:
                     # E.g. we imported `import * as fs from 'fs'` -> fs
                     # We can guess target_id is the foreign method
                     foreign_module_id = self.symbol_table[source_module][obj_name]
                     # Check if it maps to a Method in that module
                     target_id = f"{foreign_module_id}:{method_name}"
                     if target_id in self.known_method_ids:
                          edge.target_id = target_id
                          edge.call_type = CallType.MODULE_CALL
                          edge.confidence = 0.90
                          resolved.append(edge)
                          continue
                          
                # Fallback to NAME MATCHING
                if method_name in self.name_registry:
                    candidates = self.name_registry[method_name]
                    if len(candidates) == 1:
                        edge.target_id = candidates[0]
                        edge.call_type = CallType.NAME_MATCH
                        edge.confidence = 0.40
                        resolved.append(edge)
                        continue
                    else:
                        # Multiple candidates. Try locality heuristic: same file matches
                        caller_module = edge.source_id.split(':')[0]
                        file_candidates = [c for c in candidates if c.startswith(f"{caller_module}:")]
                        if len(file_candidates) == 1:
                            edge.target_id = file_candidates[0]
                            edge.call_type = CallType.NAME_MATCH
                            edge.confidence = 0.30
                            resolved.append(edge)
                            continue
                        
            # Check for dynamic dispatch pattern first
            from .external_classifier import is_dynamic_call
            if is_dynamic_call(call_text, "attribute"):
                edge.call_type = CallType.DYNAMIC
                edge.confidence = 0.0
                edge.target_id = f"dynamic:{call_text}"
                resolved.append(edge)
                continue
            
            # Unresolved
            final_type = CallType.UNRESOLVED
            if classify_call(call_text, "npm", self.project_dependencies) == "EXTERNAL":
                final_type = CallType.EXTERNAL
            else:
                # Definition-existence criterion (§2.4): if zero definitions match
                # this name anywhere in the project, the target is necessarily external.
                method_name = call_text.split('.')[-1] if '.' in call_text else call_text
                if len(self.name_registry.get(method_name, [])) == 0:
                    final_type = CallType.EXTERNAL
                
            edge.call_type = final_type
            edge.confidence = 0.0
            edge.target_id = f"external:{call_text}"
            resolved.append(edge)
            
        return resolved
