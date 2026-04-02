from ..models.call_edge import CallEdge, CallType
from ..models.method_node import MethodNode, ClassNode


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
        # import_map[module_id][local_name] = resolved_qualified_name
    ):
        # Build fast lookup indexes
        self._method_by_id: dict[str, MethodNode] = {m.id: m for m in all_methods}
        # Index methods by their short name for name-matching fallback
        self._methods_by_name: dict[str, list[MethodNode]] = {}
        for m in all_methods:
            self._methods_by_name.setdefault(m.name, []).append(m)
        self._class_by_id: dict[str, ClassNode] = {c.id: c for c in all_classes}
        self._import_map = import_map

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
            # "other" — indirect call, cannot resolve
            return CallEdge(
                source_id=caller_id,
                target_id="unresolved:indirect",
                call_type=CallType.UNRESOLVED,
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
        3. Name-match fallback: if unique match, use it with medium confidence
        4. Unresolved
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

        # Step 3: Name-match across project
        candidates = self._methods_by_name.get(name, [])
        if len(candidates) == 1:
            return CallEdge(
                source_id=caller_id, target_id=candidates[0].id,
                call_type=CallType.NAME_MATCH, line=line,
                confidence=0.5, argument_count=arg_count,
                is_conditional=is_conditional,
            )

        # Step 4: Unresolved
        return CallEdge(
            source_id=caller_id, target_id=f"unresolved:{name}",
            call_type=CallType.UNRESOLVED, line=line,
            confidence=0.0, argument_count=arg_count,
        )

    def _resolve_attribute_call(self, raw_call, caller_id, line, arg_count, is_conditional) -> CallEdge | None:
        """
        Resolve: obj.method() or self.method() or module.func()

        Resolution order:
        1. self.method() → look up in the caller's own class
        2. super().method() → look up in parent class
        3. ClassName.method() — receiver is a known class name → constructor or classmethod
        4. module.func() — receiver matches an import alias → look up in that module
        5. Name-match fallback on method name alone
        6. Unresolved
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

        # Step 2: super().method()
        if receiver == "super()" and caller_class:
            # Find parent class and look up method there
            # (full MRO resolution deferred to Phase 2)
            pass

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

        # Step 6: Unresolved
        return CallEdge(
            source_id=caller_id,
            target_id=f"unresolved:{receiver}.{attr_name}" if receiver else f"unresolved:{attr_name}",
            call_type=CallType.UNRESOLVED, line=line,
            confidence=0.0, argument_count=arg_count,
        )
