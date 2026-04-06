import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser, Node
import uuid
import os
from pathlib import Path

from ..models.method_node import MethodNode, MethodKind, ClassNode, ModuleNode
from ..models.call_edge import CallEdge, CallType, ImportEdge
from ..ingestion.project_scanner import SourceFile
from .scope_tracker import ScopeTracker, Scope


class JSASTVisitor:
    """
    Simulates an ASTVisitor using py-tree-sitter for JavaScript/TypeScript CSTs.
    Traverses the tree to find classes, methods, functions, and call sites.
    """
    def __init__(self, source_file: SourceFile, root_path: Path):
        self.source_file = source_file
        self.root_path = root_path
        
        self.methods: list[MethodNode] = []
        self.classes: list[ClassNode] = []
        # Because call sites are within methods/functions, we just store them flat
        # and attach the source method id based on scope
        self.call_edges: list[CallEdge] = []
        self.imports: list[ImportEdge] = []
        
        self.scope_tracker = ScopeTracker()
        
        self.source_code_bytes = b""
        
        # Determine language for grammar
        if source_file.language == "javascript":
            self.language = Language(tsjavascript.language())
        else:
            # We'll fallback to JS for now if TS grammar isn't loaded separately, 
            # or try to load TS if installed. We installed `tree-sitter-typescript`
            import tree_sitter_typescript as tstypescript
            # The TS module has `.typescript_language()` or similar.
            # Usually tstypescript.language_typescript() 
            if hasattr(tstypescript, "language_typescript"):
                self.language = Language(tstypescript.language_typescript())
            else:
                 self.language = Language(tsjavascript.language())

        self.parser = Parser(self.language)

    def extract(self) -> None:
        try:
            with open(self.source_file.path, 'rb') as f:
                self.source_code_bytes = f.read()
            tree = self.parser.parse(self.source_code_bytes)
            
            # Create module node logic handled by analyzer, but we do scope tracking here
            self.scope_tracker.push("module", self.source_file.module_path)
            
            self._traverse(tree.root_node)
            
            self.scope_tracker.pop()
        except Exception as e:
            print(f"Error parsing {self.source_file.path}: {e}")

    def _traverse(self, node: Node):
        """Recursively traverse the syntax tree."""
        # Note: tree-sitter processes bottom-up or top-down depending on how we crawl.
        # We'll do a simple DFS.
        node_type = node.type
        
        if node_type == "class_declaration" or node_type == "class_expression":
            self._visit_class(node)
            return  # _visit_class will traverse children
        
        elif node_type in ("function_declaration", "function_expression", "generator_function_declaration", "arrow_function"):
            self._visit_function(node)
            return  # _visit_function will traverse children
            
        elif node_type == "call_expression":
            self._visit_call_expression(node)
            
        elif node_type == "import_statement":
            self._visit_import_statement(node)
            
        elif node_type == "variable_declarator":
            # For `const x = require('y')`
            self._check_require(node)

        # Traverse children
        for child in node.children:
            self._traverse(child)

    def _visit_class(self, node: Node):
        name_node = node.child_by_field_name("name")
        class_name = self._get_text(name_node) if name_node else f"AnonymousClass_{node.start_point[0]}"
        
        class_id = f"{self.source_file.module_path}:{class_name}"
        loc = node.end_point[0] - node.start_point[0] + 1
        
        # Check extends
        parent_class = None
        # Class heritage is generic in tree-sitter, we could look for 'class_heritage' or 'extends'
        # Simplifying for now
        
        cls_node = ClassNode(
            id=class_id,
            name=class_name,
            module=self.source_file.module_path,
            file_path=self.source_file.relative_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
        )
        self.classes.append(cls_node)
        
        self.scope_tracker.push("class", class_name)
        
        # Find methods inside class_body
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "method_definition":
                    self._visit_method(child, class_name)
                else:
                    self._traverse(child)
                    
        self.scope_tracker.pop()

    def _visit_method(self, node: Node, class_name: str):
        name_node = node.child_by_field_name("name")
        method_name = self._get_text(name_node) if name_node else "<unknown>"
        
        loc = node.end_point[0] - node.start_point[0] + 1
        
        # Check if constructor, getter, setter
        kind = MethodKind.METHOD
        if method_name == "constructor":
            kind = MethodKind.CONSTRUCTOR
        elif self._get_text(node).startswith("get "):
            kind = MethodKind.GETTER
        elif self._get_text(node).startswith("set "):
            kind = MethodKind.SETTER
            
        # Is it async?
        # Tree-sitter JS often separates `async` as a child node or field
        # Simple string check for now
        if b"async " in self.source_code_bytes[node.start_byte:node.start_byte+10]:
             kind = MethodKind.ASYNC_METHOD
             
        node_id = f"{self.source_file.module_path}:{class_name}.{method_name}"
        
        m_node = MethodNode(
            id=node_id,
            name=method_name,
            qualified_name=f"{class_name}.{method_name}",
            class_name=class_name,
            module=self.source_file.module_path,
            file_path=self.source_file.relative_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            loc=loc,
            kind=kind,
            complexity=self._compute_complexity(node)
        )
        self.methods.append(m_node)
        
        self.scope_tracker.push("function", node_id)
        
        body = node.child_by_field_name("body")
        if body:
            self._traverse(body)
            
        self.scope_tracker.pop()

    def _visit_function(self, node: Node):
        name_node = node.child_by_field_name("name")
        fn_name = self._get_text(name_node) if name_node else None
        
        if not fn_name:
            parent = node.parent
            if parent:
                if parent.type == "variable_declarator":
                    name_field = parent.child_by_field_name("name")
                    if name_field:
                        fn_name = self._get_text(name_field)
                elif parent.type == "pair":
                    key_field = parent.child_by_field_name("key")
                    if key_field:
                        fn_name = self._get_text(key_field)
                elif parent.type == "assignment_expression":
                    left = parent.child_by_field_name("left")
                    if left:
                        text = self._get_text(left)
                        if "." in text:
                            fn_name = text.split(".")[-1]
                        else:
                            fn_name = text
            if not fn_name:
                fn_name = f"anonymous_{node.start_point[0]}"
        
        loc = node.end_point[0] - node.start_point[0] + 1
        
        kind = MethodKind.FUNCTION
        if node.type == "arrow_function":
            kind = MethodKind.ARROW_FUNCTION
        elif node.type == "generator_function_declaration":
            kind = MethodKind.GENERATOR
            
        if b"async " in self.source_code_bytes[node.start_byte:node.start_byte+10]:
            if kind == MethodKind.FUNCTION:
                kind = MethodKind.ASYNC_FUNCTION
                
        # Are we inside a class? If so, this is technically a nested function unless assigned to `this.`
        class_name = self.scope_tracker.current_class()
        
        prefix = f"{class_name}." if class_name else ""
        parent_fn = self.scope_tracker.current_function()
        if parent_fn:
            # Prevent deeply nested IDs from getting too long, just scope to parent fn
            node_id = f"{parent_fn}.{fn_name}"
        else:
            node_id = f"{self.source_file.module_path}:{prefix}{fn_name}"
            
        m_node = MethodNode(
            id=node_id,
            name=fn_name,
            qualified_name=f"{prefix}{fn_name}",
            class_name=class_name,
            module=self.source_file.module_path,
            file_path=self.source_file.relative_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            loc=loc,
            kind=kind,
            complexity=self._compute_complexity(node)
        )
        self.methods.append(m_node)
        
        self.scope_tracker.push("function", node_id)
        
        body = node.child_by_field_name("body")
        if body:
            self._traverse(body)
            
        self.scope_tracker.pop()

    def _visit_call_expression(self, node: Node):
        caller_id = self.scope_tracker.current_function()
        if not caller_id:
             # Module level call - we track methods, so skip or map to module-level pseudo method
             caller_id = f"{self.source_file.module_path}:<module>"
             
        function_node = node.child_by_field_name("function")
        if not function_node:
            return
            
        target_name = self._get_text(function_node)
        
        # We store target_name for resolution later. The js_call_resolver will
        # use the target_name string to assign the CallType and resolved target_id.
        edge = CallEdge(
            source_id=caller_id,
            target_id=target_name,  # Unresolved initially
            call_type=CallType.UNRESOLVED,
            line=node.start_point[0] + 1,
            confidence=0.0
        )
        self.call_edges.append(edge)
        
        # Still traverse arguments
        arguments = node.child_by_field_name("arguments")
        if arguments:
            self._traverse(arguments)

    def _visit_import_statement(self, node: Node):
        # source String
        source_node = node.child_by_field_name("source")
        if not source_node:
            return
            
        target_module_raw = self._get_text(source_node).strip("'\"")
        
        # Simple heuristic for external vs internal module
        is_external = not (target_module_raw.startswith(".") or target_module_raw.startswith("/"))
        
        imported_names = []
        
        # Check import clauses
        clause = node.child(1) # usually import_clause
        if clause and clause.type == "import_clause":
             # We can pull named imports, default imports, namespace imports
             text = self._get_text(clause)
             if "*" in text:
                 imported_names = ["*"]
             else:
                 # hacky parse for now
                 parsed_names = [n.strip() for n in text.replace("{", "").replace("}", "").split(",")]
                 imported_names = [n for n in parsed_names if n]
                 
        if not imported_names:
            imported_names = ["*"] # fallback
            
        self.imports.append(ImportEdge(
            source_module=self.source_file.module_path,
            target_module=target_module_raw, # Needs path resolution
            imported_names=imported_names,
            is_relative=not is_external,
            is_external=is_external
        ))

    def _check_require(self, node: Node):
        # variable_declarator > call_expression(require)
        value_node = node.child_by_field_name("value")
        if value_node and value_node.type == "call_expression":
            fn_node = value_node.child_by_field_name("function")
            if fn_node and self._get_text(fn_node) == "require":
                # Found a require
                args = value_node.child_by_field_name("arguments")
                if args and len(args.children) > 1:
                    target_module_raw = self._get_text(args.children[1]).strip("'\"")
                    is_external = not (target_module_raw.startswith(".") or target_module_raw.startswith("/"))
                    self.imports.append(ImportEdge(
                        source_module=self.source_file.module_path,
                        target_module=target_module_raw,
                        imported_names=["*"], # Since it's CJS assignment
                        is_relative=not is_external,
                        is_external=is_external
                    ))

    def _compute_complexity(self, node: Node) -> int:
        complexity = 1
        queue = [node]
        branching_types = {
            "if_statement", "for_statement", "while_statement", 
            "do_statement", "catch_clause", "switch_case",
            "ternary_expression"
        }
        while queue:
            curr = queue.pop(0)
            if curr.type in branching_types:
                complexity += 1
            elif curr.type == "binary_expression":
                op_node = curr.child_by_field_name("operator")
                if op_node:
                    op_text = self._get_text(op_node)
                    if op_text in ("&&", "||", "??"):
                        complexity += 1
            
            queue.extend(curr.children)
            
        return complexity

    def _get_text(self, node: Node) -> str:
        if not node:
            return ""
        return self.source_code_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")
