import ast
from dataclasses import dataclass
from .project_scanner import SourceFile


@dataclass
class ParsedSource:
    source_file: SourceFile
    source_code: str
    ast_tree: ast.Module | None        # None if parsing failed
    parse_error: str | None = None     # Error message if parsing failed


def read_and_parse(source_file: SourceFile) -> ParsedSource:
    """Read source file and parse to AST. Never raises — errors are captured."""
    try:
        with open(source_file.path, 'r', encoding='utf-8') as f:
            source_code = f.read()
            
        tree = ast.parse(source_code, filename=str(source_file.path))
        
        return ParsedSource(
            source_file=source_file,
            source_code=source_code,
            ast_tree=tree,
            parse_error=None
        )
    except SyntaxError as e:
        return ParsedSource(
            source_file=source_file,
            source_code="",
            ast_tree=None,
            parse_error=f"Syntax error: {e}"
        )
    except Exception as e:
        return ParsedSource(
            source_file=source_file,
            source_code="",
            ast_tree=None,
            parse_error=f"Error reading/parsing file: {e}"
        )
