import ast
from app.analysis.ast_visitor import ASTVisitor
from app.models.method_node import MethodKind

def test_visitor_extracts_methods_and_classes():
    code = """
import os
from typing import List

class MyClass:
    def my_method(self, x: int) -> int:
        return x + 1

def my_func():
    obj = MyClass()
    obj.my_method(1)
"""
    tree = ast.parse(code)
    visitor = ASTVisitor("test_module", "test.py", "test.py")
    result = visitor.extract(tree)
    
    assert len(result.classes) == 1
    assert result.classes[0].name == "MyClass"
    
    assert len(result.methods) == 2
    method_names = {m.name for m in result.methods}
    assert method_names == {"my_method", "my_func"}
    
    assert len(result.imports) == 2
