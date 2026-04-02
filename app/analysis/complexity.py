import ast

# AST node types that each add 1 to cyclomatic complexity
COMPLEXITY_INCREMENTORS = (
    ast.If, ast.While, ast.For, ast.AsyncFor,
    ast.ExceptHandler, ast.With, ast.AsyncWith,
    ast.Assert, ast.comprehension,
    ast.BoolOp,   # each and/or in a BoolOp adds branches
)

def compute_complexity(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """
    Compute McCabe cyclomatic complexity for a single function.

    Formula: 1 + number of branching points in the function's control flow.
    Minimum value is always 1.

    Notes:
    - Each 'if', 'while', 'for', 'except', 'with' = +1
    - Each 'and'/'or' in a BoolOp = +(num_values - 1)
    - Nested functions are counted separately; their internal complexity
      is NOT included in the enclosing function's score.
    """
    complexity = 1
    for node in ast.walk(func_node):
        # Skip nested function bodies — they are analyzed separately
        if node is not func_node and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(node, COMPLEXITY_INCREMENTORS):
            if isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            else:
                complexity += 1
    return complexity
