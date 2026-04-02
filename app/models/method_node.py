from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class MethodKind(str, Enum):
    FUNCTION = "function"          # module-level def
    METHOD = "method"              # instance method
    CLASS_METHOD = "classmethod"   # @classmethod
    STATIC_METHOD = "staticmethod" # @staticmethod
    PROPERTY = "property"          # @property
    ASYNC_FUNCTION = "async_function"
    ASYNC_METHOD = "async_method"
    LAMBDA = "lambda"              # inline lambda (limited support)


class MethodNode(BaseModel):
    # Identity
    id: str = Field(
        description="Stable unique identifier. Format: 'module.path:ClassName.method' "
                    "or 'module.path:function_name'. Example: 'app.services.user:UserService.get_user'"
    )
    name: str                      # Short name: "get_user"
    qualified_name: str            # Full name: "UserService.get_user"
    kind: MethodKind

    # Location
    file_path: str                 # Relative to project root: "app/services/user.py"
    line_start: int
    line_end: int
    module: str                    # Dotted module path: "app.services.user"
    class_name: str | None = None  # Enclosing class name, if method

    # Signature
    parameters: list[str] = []     # Parameter names (excluding self/cls)
    return_annotation: str | None = None
    decorators: list[str] = []     # Decorator names as strings
    is_async: bool = False
    docstring: str | None = None   # First line only

    # Size
    loc: int = 0                   # Lines of code in body (non-blank, non-comment)
    complexity: int = 1            # Cyclomatic complexity (min 1)

    class Config:
        use_enum_values = True


class ClassNode(BaseModel):
    id: str                        # "module.path:ClassName"
    name: str
    module: str
    file_path: str
    line_start: int
    line_end: int
    bases: list[str] = []          # Parent class names as strings
    decorator_list: list[str] = []
    method_ids: list[str] = []     # IDs of all methods in this class
    docstring: str | None = None


class ModuleNode(BaseModel):
    id: str                        # Dotted path: "app.services.user"
    file_path: str                 # "app/services/user.py"
    package: str | None = None     # Immediate package: "app.services"
    class_ids: list[str] = []
    function_ids: list[str] = []   # Top-level (non-method) function IDs
    star_imports: list[str] = []   # Modules imported with *; signals analysis gap
