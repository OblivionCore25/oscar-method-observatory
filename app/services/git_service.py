import logging
import urllib.parse
from datetime import datetime, UTC
from pathlib import Path

from ..models.git_profile import GitRepoHealth, GitFileChurn, GitAnalysisResult
from ..storage.factory import get_storage
from ..analysis.git_analyzer import GitAnalyzer

_log = logging.getLogger(__name__)

class GitService:
    def __init__(self, data_directory: Path):
        self.data_directory = data_directory
        self.storage = get_storage()
        self.git_analyzer = GitAnalyzer()

    def analyze(self, project_slug: str, ecosystem: str, package_name: str, version: str | None = None) -> GitAnalysisResult:
        decoded_package_name = urllib.parse.unquote(package_name)
        
        # 1. Resolve repo URL from registry
        repo_url = None
        if ecosystem.lower() == "npm":
            from ..ingestion.npm_downloader import resolve_repo_url_npm
            repo_url = resolve_repo_url_npm(decoded_package_name)
        elif ecosystem.lower() == "pypi":
            from ..ingestion.pypi_downloader import resolve_repo_url_pypi
            repo_url = resolve_repo_url_pypi(decoded_package_name, version=version)
            
        if not repo_url:
            raise ValueError(f"Could not auto-detect repository URL for {decoded_package_name} from registry.")
            
        _log.info(f"Auto-detected repo URL for {decoded_package_name}: {repo_url}")
        
        # 2. Clone bare repository
        # Use safe normalized slug for directory
        import re
        safe_slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', decoded_package_name)
        bare_repo_dir = self.data_directory / "downloads" / "git_repos" / safe_slug
        
        _log.info(f"Cloning {repo_url} to {bare_repo_dir}")
        bare_repo = self.git_analyzer.clone_bare(repo_url, bare_repo_dir)
        
        # 3. Extract Repo Health
        _log.info(f"Extracting repo health for {project_slug}")
        health_dict = self.git_analyzer.extract_repo_health(bare_repo)
        if not health_dict:
            raise RuntimeError("Git analyzer returned empty health data.")
            
        health = GitRepoHealth(
            project_slug=project_slug,
            repo_url=repo_url,
            analyzed_at=datetime.now(UTC),
            **health_dict
        )
        
        # 4. Extract File Churn
        _log.info(f"Extracting file churn for {project_slug}")
        churn_map = self.git_analyzer.extract_file_churn(bare_repo)
        
        files = []
        for file_path, churn in churn_map.items():
            top_authors = [{"name": name, "commits": count} for name, count in churn.authors.most_common(50)]
            files.append(
                GitFileChurn(
                    file_path=file_path,
                    commits=churn.commits,
                    author_count=len(churn.authors),
                    last_modified=churn.last_modified,
                    top_authors=top_authors
                )
            )
            
        result = GitAnalysisResult(health=health, files=files)
        
        # 5. Persist
        if hasattr(self.storage, "save_git_profile"):
            self.storage.save_git_profile(result)
            
        return result

    def load_profile(self, project_slug: str) -> GitRepoHealth | None:
        import urllib.parse
        normalized = urllib.parse.unquote(project_slug).replace("@", "").replace("/", "__")
        if hasattr(self.storage, "load_git_profile"):
            return self.storage.load_git_profile(normalized)
        return None

    def load_file_churn(self, project_slug: str) -> list[GitFileChurn]:
        import urllib.parse
        normalized = urllib.parse.unquote(project_slug).replace("@", "").replace("/", "__")
        if hasattr(self.storage, "load_git_file_churn"):
            return self.storage.load_git_file_churn(normalized)
        return []

    def load_file_churn_map(self, project_slug: str) -> dict[str, GitFileChurn]:
        import urllib.parse
        normalized = urllib.parse.unquote(project_slug).replace("@", "").replace("/", "__")
        if hasattr(self.storage, "load_git_file_churn_map"):
            return self.storage.load_git_file_churn_map(normalized)
        return {}
