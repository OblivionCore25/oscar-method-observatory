from ..models.call_edge import CallEdge, CallType, InheritanceEdge
from ..models.method_node import MethodNode, ClassNode
from .external_classifier import classify_call, is_dynamic_call


class CallResolver:
    """
    Resolves raw call site records (collected during AST visit) into
    typed CallEdge objects with confidence scores.

    Works across the entire project — receives all methods and modules
    and builds a lookup index before resolving.
    """

    def __init__(
        self,
        all_methods: list[MethodNode],
        all_classes: list[ClassNode],
        import_map: dict[str, dict[str, str]],
        all_inheritance: list[InheritanceEdge] = None,
        project_dependencies: set[str] = None
    ):
        self._project_dependencies = project_dependencies or set()
        # Build fast lookup indexes
        self._method_by_id: dict[str, MethodNode] = {m.id: m for m in all_methods}
        # Index methods by their short name for name-matching fallback
        self._methods_by_name: dict[str, list[MethodNode]] = {}
        for m in all_methods:
            self._methods_by_name.setdefault(m.name, []).append(m)
        self._class_by_id: dict[str, ClassNode] = {c.id: c for c in all_classes}
        self._classes_by_name: dict[str, list[ClassNode]] = {}
        for c in all_classes:
            self._classes_by_name.setdefault(c.name, []).append(c)
        self._import_map = import_map
        
        self._inheritance_map: dict[str, list[str]] = {}
        if all_inheritance:
            for edge in all_inheritance:
                self._inheritance_map.setdefault(edge.child_class_id, []).append(edge.parent_class_name)

    def resolve(self, raw_call: dict) -> CallEdge | None:
        """
        Attempt to resolve one raw call record into a CallEdge.
        Returns None if the call is to an external (out-of-project) function
        and we choose to drop it rather than create a placeholder.
        """
        caller_id: str = raw_call["caller_id"]
        expr_type: str = raw_call["call_expr_type"]
        line: int = raw_call["line"]
        arg_count: int = raw_call["argument_count"]
        is_conditional: bool = raw_call["is_conditional"]

        if expr_type == "name":
            return self._resolve_name_call(raw_call, caller_id, line, arg_count, is_conditional)
        elif expr_type == "attribute":
            return self._resolve_attribute_call(raw_call, caller_id, line, arg_count, is_conditional)
        else:
            # "other" — indirect call (subscript, starred, etc.), classify as DYNAMIC
            return CallEdge(
                source_id=caller_id,
                target_id="dynamic:indirect",
                call_type=CallType.DYNAMIC,
                line=line,
                confidence=0.0,
                argument_count=arg_count,
            )

    def _resolve_name_call(self, raw_call, caller_id, line, arg_count, is_conditional) -> CallEdge | None:
        """
        Resolve: func() or imported_func()

        Resolution order:
        1. Look up name in import_map for caller's module → may resolve to a project function
        2. Look up name directly as a method in the same module
        2.5. Class Constructor Name Match
        3. Name-match fallback: if unique match, use it with medium confidence
        4. Dynamic / External / Unresolved
        """
        name: str = raw_call["call_name"]
        caller_module = caller_id.rsplit(":", 1)[0] if ":" in caller_id else caller_id

        # Step 1: Check if imported from another module
        module_imports = self._import_map.get(caller_module, {})
        if name in module_imports:
            resolved = module_imports[name]
            if resolved in self._method_by_id:
                return CallEdge(
                    source_id=caller_id, target_id=resolved,
                    call_type=CallType.MODULE_CALL, line=line,
                    confidence=0.9, argument_count=arg_count,
                    is_conditional=is_conditional,
                )

        # Step 2: Same module direct lookup
        same_module_id = f"{caller_module}:{name}"
        if same_module_id in self._method_by_id:
            return CallEdge(
                source_id=caller_id, target_id=same_module_id,
                call_type=CallType.DIRECT, line=line,
                confidence=1.0, argument_count=arg_count,
                is_conditional=is_conditional,
            )

        # Step 2.5: Class Constructor Name Match
        class_candidates = self._classes_by_name.get(name, [])
        if class_candidates:
            # We match to the first class found
            class_id = class_candidates[0].id
            init_id = f"{class_id}.__init__"
            target_id = init_id if init_id in self._method_by_id else class_id
            return CallEdge(
                source_id=caller_id, target_id=target_id,
                call_type=CallType.CONSTRUCTOR, line=line,
                confidence=0.85, argument_count=arg_count,
                is_conditional=is_conditional,
            )

        # Step 3: Name-match across project
        candidates = self._methods_by_name.get(name, [])
        if len(candidates) == 1:
            return CallEdge(
                source_id=caller_id, target_id=candidates[0].id,
                call_type=CallType.NAME_MATCH, line=line,
                confidence=0.5, argument_count=arg_count,
                is_conditional=is_conditional,
            )

        # Step 4: Dynamic / External / Unresolved
        if is_dynamic_call(name, "name"):
            return CallEdge(
                source_id=caller_id, target_id=f"dynamic:{name}",
                call_type=CallType.DYNAMIC, line=line,
                confidence=0.0, argument_count=arg_count,
            )
        
        final_type = CallType.UNRESOLVED
        if classify_call(name, "pypi", self._project_dependencies) == "EXTERNAL":
            final_type = CallType.EXTERNAL
        # Definition-existence criterion (§2.4): if zero definitions match this
        # name anywhere in the project, the target is necessarily external.
        elif len(candidates) == 0 and name not in self._classes_by_name:
            final_type = CallType.EXTERNAL
            
        return CallEdge(
            source_id=caller_id, target_id=f"unresolved:{name}",
            call_type=final_type, line=line,
            confidence=0.0, argument_count=arg_count,
        )

    def _resolve_attribute_call(self, raw_call, caller_id, line, arg_count, is_conditional) -> CallEdge | None:
        """
        Resolve: obj.method() or self.method() or module.func()

        Resolution order:
        0. Type-annotation resolution (receiver has a type hint)
        1. self.method() → look up in the caller's own class
        1.5. self.method() MRO — traverse inheritance chain
        2. super().method() → look up in parent class
        3. ClassName.method() — receiver is a known class name → constructor or classmethod
        4. module.func() — receiver matches an import alias → look up in that module
        5. Name-match fallback on method name alone
        6. Dynamic / External / Unresolved
        """
        attr_name: str = raw_call["attr_name"]
        receiver: str | None = raw_call["receiver_name"]
        receiver_type: str | None = raw_call.get("receiver_type")

        caller_module = caller_id.rsplit(":", 1)[0] if ":" in caller_id else caller_id
        caller_method = self._method_by_id.get(caller_id)
        caller_class = caller_method.class_name if caller_method else None

        # Step 0: Type-Annotation resolution!
        if receiver_type:
            # We match the declared type hint straight to the available class index
            class_candidates = [c for c in self._class_by_id.values() if c.name == receiver_type or c.id == receiver_type]
            if class_candidates:
                target_id = f"{class_candidates[0].id}.{attr_name}"
                if target_id in self._method_by_id:
                    return CallEdge(
                        source_id=caller_id, target_id=target_id,
                        call_type=CallType.DIRECT, line=line,
                        confidence=0.9, argument_count=arg_count,
                        is_conditional=is_conditional,
                    )

        # Step 1: self.method() resolution
        if receiver == "self" and caller_class:
            target_id = f"{caller_module}:{caller_class}.{attr_name}"
            if target_id in self._method_by_id:
                return CallEdge(
                    source_id=caller_id, target_id=target_id,
                    call_type=CallType.SELF_CALL, line=line,
                    confidence=0.95, argument_count=arg_count,
                    is_conditional=is_conditional,
                )
            
            # Step 1.5: MRO traversal — method is inherited from parent
            caller_class_id = f"{caller_module}:{caller_class}"
            mro_result = self._resolve_via_mro(caller_class_id, attr_name, caller_id, line, arg_count, is_conditional)
            if mro_result:
                return mro_result

        # Step 2: super().method()
        if receiver == "super()" and caller_class:
            caller_class_id = f"{caller_module}:{caller_class}"
            parent_names = self._inheritance_map.get(caller_class_id, [])
            for parent_name in parent_names:
                # check all project classes that match the parent name
                parent_classes = self._classes_by_name.get(parent_name, [])
                for pc in parent_classes:
                    super_method_id = f"{pc.id}.{attr_name}"
                    if super_method_id in self._method_by_id:
                        return CallEdge(
                            source_id=caller_id, target_id=super_method_id,
                            call_type=CallType.SUPER_CALL, line=line,
                            confidence=0.8, argument_count=arg_count,
                            is_conditional=is_conditional,
                        )

        # Step 3: ClassName() — constructor call
        # receiver is None for Name calls but attr_name may be "__init__"
        # If receiver is a known class name, resolve to __init__
        if receiver:
            class_id = f"{caller_module}:{receiver}"
            if class_id in self._class_by_id:
                init_id = f"{class_id}.__init__"
                target_id = init_id if init_id in self._method_by_id else class_id
                return CallEdge(
                    source_id=caller_id, target_id=target_id,
                    call_type=CallType.CONSTRUCTOR, line=line,
                    confidence=0.9, argument_count=arg_count,
                    is_conditional=is_conditional,
                )

        # Step 4: module.func() via import alias
        if receiver:
            module_imports = self._import_map.get(caller_module, {})
            if receiver in module_imports:
                target_module = module_imports[receiver]
                target_id = f"{target_module}:{attr_name}"
                if target_id in self._method_by_id:
                    return CallEdge(
                        source_id=caller_id, target_id=target_id,
                        call_type=CallType.MODULE_CALL, line=line,
                        confidence=0.85, argument_count=arg_count,
                        is_conditional=is_conditional,
                    )

        # Step 5: Name-match on method name
        candidates = self._methods_by_name.get(attr_name, [])
        if len(candidates) == 1:
            return CallEdge(
                source_id=caller_id, target_id=candidates[0].id,
                call_type=CallType.NAME_MATCH, line=line,
                confidence=0.4, argument_count=arg_count,
                is_conditional=is_conditional,
            )
        elif len(candidates) > 1:
            if receiver == "self" and caller_class:
                # Check parent classes
                caller_class_id = f"{caller_module}:{caller_class}"
                parent_names = self._inheritance_map.get(caller_class_id, [])
                parent_candidates = []
                for p_name in parent_names:
                    p_classes = self._classes_by_name.get(p_name, [])
                    for p_c in p_classes:
                        p_meth = f"{p_c.id}.{attr_name}"
                        if p_meth in self._method_by_id:
                            parent_candidates.append(p_meth)
                if len(parent_candidates) == 1:
                    return CallEdge(
                        source_id=caller_id, target_id=parent_candidates[0],
                        call_type=CallType.SUPER_CALL, line=line,
                        confidence=0.7, argument_count=arg_count,
                        is_conditional=is_conditional,
                    )
            
            # Locality heuristic: same module matches
            caller_module = caller_id.split(':')[0]
            file_candidates = [c for c in candidates if c.id.startswith(f"{caller_module}:")]
            if len(file_candidates) == 1:
                return CallEdge(
                    source_id=caller_id, target_id=file_candidates[0].id,
                    call_type=CallType.NAME_MATCH, line=line,
                    confidence=0.3, argument_count=arg_count,
                    is_conditional=is_conditional,
                )

        # Step 6: Dynamic / External / Unresolved
        target_name = f"{receiver}.{attr_name}" if receiver else attr_name
        
        # Check if this is a dynamic dispatch pattern
        if is_dynamic_call(target_name, "attribute"):
            return CallEdge(
                source_id=caller_id,
                target_id=f"dynamic:{target_name}",
                call_type=CallType.DYNAMIC, line=line,
                confidence=0.0, argument_count=arg_count,
            )
        
        final_type = CallType.UNRESOLVED
        if classify_call(target_name, "pypi", self._project_dependencies) == "EXTERNAL":
            final_type = CallType.EXTERNAL
        else:
            # Definition-existence criterion (§2.4): if zero definitions match
            # this method name anywhere in the project, the target is necessarily external.
            method_name = attr_name
            method_candidates = self._methods_by_name.get(method_name, [])
            class_candidates = self._classes_by_name.get(method_name, [])
            if len(method_candidates) == 0 and len(class_candidates) == 0:
                final_type = CallType.EXTERNAL
            
        return CallEdge(
            source_id=caller_id,
            target_id=f"unresolved:{target_name}",
            call_type=final_type, line=line,
            confidence=0.0, argument_count=arg_count,
        )

    def _resolve_via_mro(self, class_id: str, method_name: str, 
                          caller_id: str, line: int, arg_count: int,
                          is_conditional: bool) -> CallEdge | None:
        """
        Traverse the Method Resolution Order (MRO) to find an inherited method.
        Uses BFS over the inheritance chain.
        """
        visited = set()
        queue = [class_id]
        
        while queue:
            current_class_id = queue.pop(0)
            if current_class_id in visited:
                continue
            visited.add(current_class_id)
            
            parent_names = self._inheritance_map.get(current_class_id, [])
            for parent_name in parent_names:
                parent_classes = self._classes_by_name.get(parent_name, [])
                for pc in parent_classes:
                    target_id = f"{pc.id}.{method_name}"
                    if target_id in self._method_by_id:
                        return CallEdge(
                            source_id=caller_id, target_id=target_id,
                            call_type=CallType.SELF_CALL, line=line,
                            confidence=0.75, argument_count=arg_count,
                            is_conditional=is_conditional,
                        )
                    # Continue traversing up the hierarchy
                    queue.append(pc.id)
        
        return None
