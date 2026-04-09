from datetime import datetime
from pydantic import BaseModel


class GitRepoHealth(BaseModel):
    project_slug: str
    repo_url: str
    analyzed_at: datetime
    total_commits: int = 0
    total_contributors: int = 0
    active_contributors_90d: int = 0
    bus_factor: int = 0
    first_commit_date: str | None = None
    last_commit_date: str | None = None
    days_since_last_commit: int = 0
    commits_in_window: int = 0
    analysis_window_days: int = 365
    monthly_commit_series: list[dict] = []
    top_contributors: list[dict] = []


class GitFileChurn(BaseModel):
    file_path: str
    commits: int = 0
    author_count: int = 0
    last_modified: str | None = None
    top_authors: list[dict] = []


class GitAnalysisResult(BaseModel):
    health: GitRepoHealth
    files: list[GitFileChurn]
