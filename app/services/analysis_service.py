from pathlib import Path
from ..models.analysis_result import AnalysisResult
from ..storage.factory import get_storage
from ..analysis.python_analyzer import PythonAnalyzer

class UnsupportedEcosystemError(Exception):
    pass

class AnalysisService:

    def __init__(self, data_directory: Path, oscar_version: str = "0.1.0", max_file_size_kb: int = 500):
        self.data_directory = data_directory
        self.oscar_version = oscar_version
        self.max_file_size_kb = max_file_size_kb
        self.storage = get_storage()
        
        # Register available analyzers
        self._analyzers = {
            "pypi": PythonAnalyzer(),
            # Future: "npm": JavaScriptAnalyzer()
        }

    def analyze(self, project_path: str, project_slug: str, ecosystem: str = "pypi", exclude_tests: bool = False) -> AnalysisResult:
        """
        Routes the extraction request to the appropriate ecosystem analyzer.
        """
        analyzer = self._analyzers.get(ecosystem.lower())
        if not analyzer:
            raise UnsupportedEcosystemError(f"Internal structure extraction for ecosystem '{ecosystem}' is not yet supported.")
            
        root = Path(project_path).resolve()
        
        result = analyzer.analyze(
            project_path=root,
            project_slug=project_slug,
            exclude_tests=exclude_tests,
            max_file_size_kb=self.max_file_size_kb,
            oscar_version=self.oscar_version
        )

        # Persist the output globally
        self.storage.save(project_slug, result)

        return result

    def load(self, project_slug: str) -> AnalysisResult | None:
        return self.storage.load(project_slug)

    def list_projects(self) -> list[str]:
        return self.storage.list_projects()
