from ..models.method_node import MethodNode, ModuleNode, ClassNode
from ..models.call_edge import ImportEdge

class ProjectSymbolTable:
    """
    Builds a project-wide mapping from local names within modules
    to their fully qualified definitions (Method IDs or Class IDs).
    Follows import chains transitively.
    """
    def __init__(self):
        # module_id -> local_name -> global_node_id
        self._table: dict[str, dict[str, str]] = {}

    def build(self,
              modules: list[ModuleNode],
              imports: list[ImportEdge],
              methods: list[MethodNode],
              classes: list[ClassNode]) -> dict[str, dict[str, str]]:
        
        # 1. Initialize tables
        for m in modules:
            self._table[m.id] = {}

        # 2. Build a module alias map for resolving short names → full IDs
        # E.g., "flask" → "src.flask", "helpers" → "src.flask.helpers"
        module_ids = set(self._table.keys())
        self._module_alias_map: dict[str, str] = {}
        for mid in module_ids:
            # Map the last component: "src.flask.helpers" → "helpers"
            parts = mid.split(".")
            for i in range(len(parts)):
                suffix = ".".join(parts[i:])
                # Only map if unambiguous (or prefer longer match)
                if suffix not in self._module_alias_map:
                    self._module_alias_map[suffix] = mid

        # 3. Register native declarations (classes and top-level functions)
        for cls in classes:
            if cls.module in self._table:
                self._table[cls.module][cls.name] = cls.id
                
        for m in methods:
            if not m.class_name and m.module in self._table:
                self._table[m.module][m.name] = m.id

        # 4. Iteratively resolve imports (transitive closure)
        changed = True
        passes = 0
        while changed and passes < 10:
            changed = False
            passes += 1
            
            for imp in imports:
                if imp.is_external:
                    continue
                
                src = imp.source_module
                tgt = imp.target_module
                
                # Normalize target module using alias map if not found directly
                if tgt not in self._table:
                    resolved_tgt = self._resolve_module_alias(tgt)
                    if resolved_tgt:
                        tgt = resolved_tgt
                
                if src not in self._table or tgt not in self._table:
                    continue
                
                if imp.imported_names == ["*"]:
                    for name, global_id in self._table[tgt].items():
                        if not name.startswith("_"):
                            if self._table[src].get(name) != global_id:
                                self._table[src][name] = global_id
                                changed = True
                else:
                    for name in imp.imported_names:
                        if name in self._table[tgt]:
                            global_id = self._table[tgt][name]
                            # Handle aliases dynamically if it was recorded
                            local_name = imp.alias if (imp.alias and len(imp.imported_names) == 1) else name
                            if self._table[src].get(local_name) != global_id:
                                self._table[src][local_name] = global_id
                                changed = True

        return self._table

    def _resolve_module_alias(self, target: str) -> str | None:
        """
        Attempt to resolve a module name that doesn't match any known module ID.
        
        Examples:
            "flask"      → "src.flask"       (prefix missing)
            "src.helpers" → "src.flask.helpers" (intermediate package missing)
            "helpers"    → "src.flask.helpers" (short name)
        """
        # Direct alias lookup
        if target in self._module_alias_map:
            return self._module_alias_map[target]
        
        # Try suffix matching: "flask" could match "src.flask"
        for mid in self._table:
            if mid.endswith(f".{target}") or mid.endswith(f".{target.replace('.', '.')}"):
                return mid
        
        return None
