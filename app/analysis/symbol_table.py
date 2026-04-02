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

        # 2. Register native declarations (classes and top-level functions)
        for cls in classes:
            if cls.module in self._table:
                self._table[cls.module][cls.name] = cls.id
                
        for m in methods:
            if not m.class_name and m.module in self._table:
                self._table[m.module][m.name] = m.id

        # 3. Iteratively resolve imports (transitive closure)
        changed = True
        passes = 0
        while changed and passes < 5:
            changed = False
            passes += 1
            
            for imp in imports:
                if imp.is_external:
                    continue
                
                src = imp.source_module
                tgt = imp.target_module
                
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
