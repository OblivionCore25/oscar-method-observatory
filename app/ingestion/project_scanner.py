from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

# Directories to always skip
DEFAULT_EXCLUDE_DIRS = {
    "__pycache__", ".venv", "venv", "env", ".env",
    "node_modules", ".git", ".tox", "dist", "build", ".next", "coverage",
    "*.egg-info", ".mypy_cache", ".pytest_cache",
    # Non-production code: consumer-side examples, docs, benchmarks, tests
    "examples", "example", "docs", "doc", "benchmarks", "benchmark", "bench",
    "test", "tests", "__tests__", "fixtures", "spec",
}

@dataclass
class ScanConfig:
    root_path: Path
    exclude_dirs: set[str] = field(default_factory=lambda: DEFAULT_EXCLUDE_DIRS.copy())
    exclude_tests: bool = False        # If True, skip test_*.py and tests/ directories
    max_file_size_kb: int = 500        # Skip files larger than this (likely generated code)

@dataclass
class SourceFile:
    path: Path
    relative_path: str                 # Relative to project root
    module_path: str                   # Dotted module path: "app.services.user"
    language: str                      # "python", "javascript", "typescript"
    size_bytes: int


def scan_project(config: ScanConfig) -> list[SourceFile]:
    """Walk the project directory and return all relevant files to analyze."""
    source_files = []
    
    for root_dir, dirs, files in os.walk(config.root_path):
        # Modify dirs in-place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in config.exclude_dirs]
        
        if config.exclude_tests:
            dirs[:] = [d for d in dirs if d != "tests" and not d.endswith("_tests") and d != "__tests__" and d != "test"]

        for file_name in files:
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in (".py", ".js", ".mjs", ".jsx", ".ts", ".tsx"):
                continue
                
            if config.exclude_tests:
                if file_name.startswith("test_") or file_name.endswith("_test.py") or file_name.endswith(".test.js") or file_name.endswith(".spec.js") or file_name.endswith(".test.ts") or file_name.endswith(".spec.ts"):
                    continue

            file_path = Path(root_dir) / file_name
            
            try:
                size_bytes = file_path.stat().st_size
                if size_bytes > config.max_file_size_kb * 1024:
                    continue
            except OSError:
                continue

            relative_path_obj = file_path.relative_to(config.root_path)
            
            if ext == ".py":
                module_path = path_to_module(file_path, config.root_path)
                lang = "python"
            else:
                module_path = path_to_module_js(file_path, config.root_path)
                lang = "typescript" if ext in (".ts", ".tsx") else "javascript"

            source_files.append(SourceFile(
                path=file_path,
                relative_path=str(relative_path_obj),
                module_path=module_path,
                language=lang,
                size_bytes=size_bytes
            ))

    return source_files


def path_to_module(file_path: Path, root: Path) -> str:
    """Convert a file path to a dotted Python module path.

    Example: /project/app/services/user.py → app.services.user
    Handles __init__.py → parent package name.
    """
    rel_path = file_path.relative_to(root)
    parts = list(rel_path.parts)
    
    if not parts:
        return ""
        
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = parts[-1][:-3]  # remove .py
        
    return ".".join(parts)

def path_to_module_js(file_path: Path, root: Path) -> str:
    """Convert a file path to a JS module identifier.
    Example: /project/src/utils.js -> src/utils
    Handes index.js -> parent folder name.
    """
    rel_path = file_path.relative_to(root)
    parts = list(rel_path.parts)
    
    if not parts:
        return ""
        
    if parts[-1] in ("index.js", "index.mjs", "index.jsx", "index.ts", "index.tsx"):
        parts.pop()
    else:
        # remove extension
        filename = parts[-1]
        ext = os.path.splitext(filename)[1]
        parts[-1] = filename[:-len(ext)]
        
    return "/".join(parts)
