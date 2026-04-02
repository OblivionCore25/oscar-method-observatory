import ast
from dataclasses import dataclass, field
from ..models.method_node import MethodNode, ClassNode, ModuleNode, MethodKind
from ..models.call_edge import CallEdge, ImportEdge, InheritanceEdge, CallType
from .scope_tracker import ScopeTracker
from .complexity import compute_complexity


@dataclass
class FileExtractionResult:
    """All entities extracted from a single source file."""
    module: ModuleNode
    methods: list[MethodNode] = field(default_factory=list)
    classes: list[ClassNode] = field(default_factory=list)
    raw_calls: list[dict] = field(default_factory=list)    # Pre-resolution call data
    imports: list[ImportEdge] = field(default_factory=list)
    inheritance: list[InheritanceEdge] = field(default_factory=list)


class ASTVisitor(ast.NodeVisitor):
    """
    Single-pass visitor over one Python module's AST.
    Extracts: method definitions, class definitions, call sites, imports.
    Does NOT resolve cross-file calls — that is done in CallResolver.
    """

    def __init__(self, module_id: str, file_path: str, relative_path: str):
        self.module_id = module_id
        self.file_path = file_path
        self.relative_path = relative_path
        self.scope = ScopeTracker()
        self.result = FileExtractionResult(
            module=ModuleNode(id=module_id, file_path=relative_path)
        )
        # Stack of class contexts for nested class support
        self._class_stack: list[str] = []
        # Stack of function contexts (qualified names)
        self._function_stack: list[str] = []

    # ------------------------------------------------------------------ #
    #  Entry Point                                                         #
    # ------------------------------------------------------------------ #

    def extract(self, tree: ast.Module) -> FileExtractionResult:
        self.scope.push("module", self.module_id)
        self.visit(tree)
        self.scope.pop()
        return self.result

    # ------------------------------------------------------------------ #
    #  Import Handling                                                     #
    # ------------------------------------------------------------------ #

    def visit_Import(self, node: ast.Import) -> None:
        """Handle: import foo, import foo.bar as baz"""
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".")[0]
            self.scope.record_import(local_name, alias.name)
            self.result.imports.append(ImportEdge(
                source_module=self.module_id,
                target_module=alias.name,
                imported_names=[alias.name],
                alias=alias.asname,
                is_external=self._is_external_module(alias.name),
            ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle: from foo import bar, from . import baz"""
        module = node.module or ""
        is_relative = node.level > 0
        imported_names = [alias.name for alias in node.names]

        # Record each imported name in scope
        for alias in node.names:
            local_name = alias.asname or alias.name
            full_qualified = f"{module}.{alias.name}" if module else alias.name
            self.scope.record_import(local_name, full_qualified)

        is_star = imported_names == ["*"]
        if is_star:
            self.result.module.star_imports.append(module)

        self.result.imports.append(ImportEdge(
            source_module=self.module_id,
            target_module=module,
            imported_names=imported_names,
            is_relative=is_relative,
            is_external=self._is_external_module(module),
        ))
        self.generic_visit(node)

    # ------------------------------------------------------------------ #
    #  Class Definitions                                                   #
    # ------------------------------------------------------------------ #

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_id = f"{self.module_id}:{node.name}"
        decorators = [self._decorator_name(d) for d in node.decorator_list]

        # Extract base class names (best-effort string representation)
        bases = [ast.unparse(b) for b in node.bases]

        class_node = ClassNode(
            id=class_id,
            name=node.name,
            module=self.module_id,
            file_path=self.relative_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            bases=bases,
            decorator_list=decorators,
            docstring=self._extract_docstring(node),
        )
        self.result.classes.append(class_node)
        self.result.module.class_ids.append(class_id)

        # Add inheritance edges for each base
        for base_name in bases:
            self.result.inheritance.append(InheritanceEdge(
                child_class_id=class_id,
                parent_class_name=base_name,
                parent_class_id=None,   # resolved later in Phase 2
            ))

        # Bind the class name in the current module scope
        self.scope.bind(node.name, class_id)

        # Descend into class body with class context
        self._class_stack.append(node.name)
        self.scope.push("class", node.name)
        self.generic_visit(node)
        self.scope.pop()
        self._class_stack.pop()

        # Populate method_ids on the class node
        class_node.method_ids = [
            m.id for m in self.result.methods
            if m.class_name == node.name and m.module == self.module_id
        ]

    # ------------------------------------------------------------------ #
    #  Function / Method Definitions                                       #
    # ------------------------------------------------------------------ #

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node, is_async=True)

    def _handle_function(self, node, is_async: bool) -> None:
        enclosing_class = self._class_stack[-1] if self._class_stack else None

        # Compute qualified name and ID
        if enclosing_class:
            qualified_name = f"{enclosing_class}.{node.name}"
            method_id = f"{self.module_id}:{qualified_name}"
        else:
            qualified_name = node.name
            method_id = f"{self.module_id}:{node.name}"

        decorators = [self._decorator_name(d) for d in node.decorator_list]
        kind = self._determine_kind(decorators, enclosing_class, is_async)

        # Extract parameters (skip self/cls)
        params = self._extract_params(node.args, kind)

        # Return annotation
        return_annotation = None
        if node.returns:
            try:
                return_annotation = ast.unparse(node.returns)
            except Exception:
                pass

        # Compute complexity and LOC
        complexity = compute_complexity(node)
        loc = self._count_loc(node)

        method_node = MethodNode(
            id=method_id,
            name=node.name,
            qualified_name=qualified_name,
            kind=kind,
            file_path=self.relative_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            module=self.module_id,
            class_name=enclosing_class,
            parameters=params,
            return_annotation=return_annotation,
            decorators=decorators,
            is_async=is_async,
            docstring=self._extract_docstring(node),
            loc=loc,
            complexity=complexity,
        )
        self.result.methods.append(method_node)

        # Bind in scope
        self.scope.bind(node.name, method_id)
        if not enclosing_class:
            self.result.module.function_ids.append(method_id)

        # Descend into function body (will encounter Call nodes)
        self._function_stack.append(method_id)
        self.scope.push("function", method_id)
        
        # Record parameter type annotations into the current scope
        self._record_param_types(node.args)
        
        self.generic_visit(node)
        self.scope.pop()
        self._function_stack.pop()

    # ------------------------------------------------------------------ #
    #  Call Sites                                                          #
    # ------------------------------------------------------------------ #

    def visit_Call(self, node: ast.Call) -> None:
        """Record every call site encountered. Resolution happens later."""
        if not self._function_stack:
            # Top-level call (module initialization); record as module-level
            caller_id = f"{self.module_id}:<module>"
        else:
            caller_id = self._function_stack[-1]

        raw_call = {
            "caller_id": caller_id,
            "line": node.lineno,
            "argument_count": len(node.args) + len(node.keywords),
            "call_expr_type": None,   # "name", "attribute", "other"
            "call_name": None,        # For Name calls: the function name
            "attr_name": None,        # For Attribute calls: the method name
            "receiver_name": None,    # For Attribute calls: the receiver name
            "is_conditional": self._is_in_conditional(),
        }

        func = node.func
        if isinstance(func, ast.Name):
            raw_call["call_expr_type"] = "name"
            raw_call["call_name"] = func.id
        elif isinstance(func, ast.Attribute):
            raw_call["call_expr_type"] = "attribute"
            raw_call["attr_name"] = func.attr
            # Best-effort receiver name extraction
            receiver_name = self._extract_receiver_name(func.value)
            raw_call["receiver_name"] = receiver_name
            if receiver_name:
                raw_call["receiver_type"] = self.scope.resolve_type(receiver_name)
            else:
                raw_call["receiver_type"] = None
        else:
            raw_call["call_expr_type"] = "other"  # indirect call, lambda, etc.
            raw_call["receiver_type"] = None

        self.result.raw_calls.append(raw_call)
        self.generic_visit(node)

    # ------------------------------------------------------------------ #
    #  Helper Methods                                                      #
    # ------------------------------------------------------------------ #

    def _determine_kind(self, decorators: list[str], class_name: str | None, is_async: bool) -> MethodKind:
        if "classmethod" in decorators:
            return MethodKind.CLASS_METHOD
        if "staticmethod" in decorators:
            return MethodKind.STATIC_METHOD
        if "property" in decorators:
            return MethodKind.PROPERTY
        if class_name:
            return MethodKind.ASYNC_METHOD if is_async else MethodKind.METHOD
        return MethodKind.ASYNC_FUNCTION if is_async else MethodKind.FUNCTION

    def _extract_params(self, args: ast.arguments, kind: MethodKind) -> list[str]:
        all_params = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
        if args.vararg:
            all_params.append(f"*{args.vararg.arg}")
        if args.kwarg:
            all_params.append(f"**{args.kwarg.arg}")
        # Remove self / cls
        if kind in (MethodKind.METHOD, MethodKind.ASYNC_METHOD, MethodKind.PROPERTY):
            return all_params[1:]   # drop self
        if kind == MethodKind.CLASS_METHOD:
            return all_params[1:]   # drop cls
        return all_params

    def _extract_docstring(self, node) -> str | None:
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            first_line = node.body[0].value.value.strip().split("\n")[0]
            return first_line[:200]  # cap at 200 chars
        return None

    def _decorator_name(self, node: ast.expr) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return "<unknown>"

    def _extract_receiver_name(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._extract_receiver_name(node.value)}.{node.attr}"
        return None

    def _is_external_module(self, module: str) -> bool:
        # Heuristic: if the module doesn't start with a local package name, treat as external.
        # This is refined by the CallResolver once the full project module list is known.
        STDLIB_PREFIXES = {"os", "sys", "re", "ast", "json", "pathlib", "typing",
                           "collections", "functools", "itertools", "datetime",
                           "logging", "unittest", "abc", "enum", "dataclasses"}
        root = module.split(".")[0]
        return root in STDLIB_PREFIXES  # Phase 1: stdlib only; Phase 2: all non-project

    def _count_loc(self, node) -> int:
        """Count non-blank, non-comment lines in function body."""
        if not hasattr(node, 'end_lineno') or node.end_lineno is None:
            return 0
        return max(0, (node.end_lineno - node.lineno) - 1)

    def _is_in_conditional(self) -> bool:
        # Simplified: always False in Phase 1.
        # Phase 2: track If/Try/While stack during traversal.
        return False

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Capture explicit type annotations on variables."""
        target = node.target
        annotation = getattr(node, "annotation", None)
        if hasattr(target, "id") and annotation is not None:
            try:
                type_name = ast.unparse(annotation)
                self.scope.bind_type(getattr(target, "id"), type_name)
            except Exception:
                pass
        self.generic_visit(node)

    def _record_param_types(self, args: ast.arguments) -> None:
        """Capture type annotations assigned to function parameters."""
        for arg in args.posonlyargs + args.args + args.kwonlyargs:
            annotation = getattr(arg, "annotation", None)
            if annotation is not None:
                try:
                    self.scope.bind_type(arg.arg, ast.unparse(annotation))
                except Exception:
                    pass
        
        vararg = getattr(args, "vararg", None)
        if vararg is not None:
            var_ann = getattr(vararg, "annotation", None)
            if var_ann is not None:
                try:
                    self.scope.bind_type(vararg.arg, ast.unparse(var_ann))
                except Exception: pass
                
        kwarg = getattr(args, "kwarg", None)
        if kwarg is not None:
            kw_ann = getattr(kwarg, "annotation", None)
            if kw_ann is not None:
                try:
                    self.scope.bind_type(kwarg.arg, ast.unparse(kw_ann))
                except Exception: pass
