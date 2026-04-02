from dataclasses import dataclass, field
from typing import Any


@dataclass
class Scope:
    kind: str                          # "module" | "class" | "function"
    name: str                          # Name of the scope owner
    bindings: dict[str, str] = field(default_factory=dict)
    type_annotations: dict[str, str] = field(default_factory=dict)
    # bindings: local name → resolved qualified name
    # e.g., {"np": "numpy", "UserService": "app.services.user:UserService"}


class ScopeTracker:
    def __init__(self):
        self._stack: list[Scope] = []
        self._all_imports: dict[str, str] = {}  # local alias -> module

    def push(self, kind: str, name: str) -> None:
        """Enter a new scope (module, class, or function)."""
        self._stack.append(Scope(kind=kind, name=name))

    def pop(self) -> Scope:
        """Exit the current scope."""
        return self._stack.pop()

    def current(self) -> Scope | None:
        """Return the innermost scope."""
        return self._stack[-1] if self._stack else None

    def current_class(self) -> str | None:
        """Return the name of the enclosing class, if any."""
        for scope in reversed(self._stack):
            if scope.kind == "class":
                return scope.name
        return None

    def current_function(self) -> str | None:
        """Return the name of the enclosing function, if any."""
        for scope in reversed(self._stack):
            if scope.kind == "function":
                return scope.name
        return None

    def bind(self, local_name: str, resolved_name: str) -> None:
        """Record a name binding in the current scope."""
        if self._stack:
            self._stack[-1].bindings[local_name] = resolved_name

    def resolve(self, name: str) -> str | None:
        """Look up a name from innermost to outermost scope."""
        for scope in reversed(self._stack):
            if name in scope.bindings:
                return scope.bindings[name]
        return None

    def bind_type(self, local_name: str, type_name: str) -> None:
        """Record a type annotation for a local variable or parameter."""
        if self._stack:
            self._stack[-1].type_annotations[local_name] = type_name

    def resolve_type(self, name: str) -> str | None:
        """Look up a type annotation from innermost to outermost scope."""
        for scope in reversed(self._stack):
            if name in scope.type_annotations:
                return scope.type_annotations[name]
        return None

    def record_import(self, local_name: str, module: str) -> None:
        """Record an import alias: 'import numpy as np' or 'from mod import func'."""
        self._all_imports[local_name] = module
        self.bind(local_name, module)
        
    def get_all_imports(self) -> dict[str, str]:
        return self._all_imports
