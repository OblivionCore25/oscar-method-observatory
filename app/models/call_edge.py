from enum import Enum
from pydantic import BaseModel, Field


class CallType(str, Enum):
    DIRECT = "direct"              # func() — resolved to known definition
    SELF_CALL = "self_call"        # self.method() — resolved within same class
    SUPER_CALL = "super_call"      # super().method()
    CONSTRUCTOR = "constructor"    # ClassName() — resolved to __init__
    MODULE_CALL = "module_call"    # module.func() — resolved via import
    NAME_MATCH = "name_match"      # obj.method() — target matched by name only, type unknown
    UNRESOLVED = "unresolved"      # call target could not be determined at all


class CallEdge(BaseModel):
    source_id: str                 # Caller method ID
    target_id: str                 # Callee method ID (or "external:module.func" for unknowns)
    call_type: CallType
    line: int                      # Line number of call site in source file
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="1.0=statically certain, 0.7=self-call, 0.5=name-matched, 0.0=unresolved"
    )
    is_conditional: bool = False   # Call site is inside an if/try/except block
    argument_count: int = 0

    class Config:
        use_enum_values = True


class ImportEdge(BaseModel):
    source_module: str             # Importing module ID
    target_module: str             # Imported module ID (or best-effort for external)
    imported_names: list[str]      # Specific names, or ["*"] for star import
    alias: str | None = None       # "import numpy as np" → alias="np"
    is_relative: bool = False
    is_external: bool = False      # True if target is a third-party/stdlib package


class InheritanceEdge(BaseModel):
    child_class_id: str
    parent_class_name: str         # String name (may not resolve to a ClassNode if external)
    parent_class_id: str | None = None  # Resolved ID if parent is within project
    mro_position: int = 0
