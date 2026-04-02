import ast
from app.analysis.complexity import compute_complexity

def test_complexity_simple():
    code = """
def simple():
    pass
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    assert compute_complexity(func_node) == 1

def test_complexity_branches():
    code = """
def complex_func(x):
    if x > 0:
        for i in range(x):
            print(i)
    elif x == 0:
        pass
    else:
        while True:
            break
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    # 1 (base) + if (+1) + for (+1) + elif pseudo-if (+1) + while (+1) = 5
    assert compute_complexity(func_node) == 5

def test_complexity_boolop():
    code = """
def check(a, b, c):
    if a and b or c:
        return True
    return False
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    # base(1) + if(1) + BoolOp 'a and b or c' has 3 values, so +2 = 4
    assert compute_complexity(func_node) == 4
