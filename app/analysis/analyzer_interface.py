from abc import ABC, abstractmethod
from pathlib import Path
from ..models.analysis_result import AnalysisResult

class LanguageAnalyzer(ABC):
    """
    Base contract for extracting structural data from different programming languages.
    Implementing classes (e.g., PythonAnalyzer, JavaScriptAnalyzer) are responsible for
    scanning the source directory, parsing files, resolving calls, and returning a uniform
    AnalysisResult representation of the project's internal architecture.
    """
    
    @abstractmethod
    def analyze(
        self, 
        project_path: Path, 
        project_slug: str, 
        exclude_tests: bool = False, 
        max_file_size_kb: int = 500,
        oscar_version: str = "0.1.0"
    ) -> AnalysisResult:
        """
        Ingest the source code directory and extract nodes, edges, and structural metrics.
        """
        pass
