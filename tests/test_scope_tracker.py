from app.analysis.scope_tracker import ScopeTracker

def test_scope_tracker_push_pop():
    tracker = ScopeTracker()
    tracker.push("module", "my_module")
    assert tracker.current().name == "my_module"
    
    tracker.push("class", "MyClass")
    assert tracker.current_class() == "MyClass"
    
    tracker.push("function", "my_method")
    assert tracker.current_function() == "my_method"
    
    tracker.pop()
    assert tracker.current_function() is None
    assert tracker.current_class() == "MyClass"

def test_scope_tracker_bind_resolve():
    tracker = ScopeTracker()
    tracker.push("module", "M")
    tracker.bind("local_var", "resolved_var")
    
    tracker.push("function", "F")
    tracker.bind("inner_var", "resolved_inner")
    
    assert tracker.resolve("local_var") == "resolved_var"
    assert tracker.resolve("inner_var") == "resolved_inner"
    assert tracker.resolve("missing") is None

def test_scope_tracker_imports():
    tracker = ScopeTracker()
    tracker.push("module", "M")
    tracker.record_import("np", "numpy")
    
    assert tracker.resolve("np") == "numpy"
    assert tracker.get_all_imports() == {"np": "numpy"}
