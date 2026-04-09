from sqlalchemy import Column, Integer, String, Float, Text, DateTime, PrimaryKeyConstraint, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class AnalysisRunModel(Base):
    __tablename__ = "analysis_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_slug = Column(String, nullable=False)
    analyzed_at = Column(String, nullable=False) # Store isoformat string
    meta_json = Column(Text, nullable=False)


class MethodNodeModel(Base):
    __tablename__ = "methods"
    
    id = Column(String, primary_key=True)
    run_id = Column(Integer, primary_key=True)
    project_slug = Column(String, nullable=True)
    name = Column(String, nullable=True)
    module = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    complexity = Column(Integer, nullable=True)
    loc = Column(Integer, nullable=True)
    change_frequency = Column(Integer, default=0, nullable=True)  # DEPRECATED: See GitFileChurnModel
    author_count = Column(Integer, default=0, nullable=True)      # DEPRECATED: See GitFileChurnModel
    last_modified = Column(String, nullable=True)                 # DEPRECATED: See GitFileChurnModel
    json_data = Column(Text, nullable=True)


class CallEdgeModel(Base):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, nullable=True)
    project_slug = Column(String, nullable=True)
    source_id = Column(String, nullable=True)
    target_id = Column(String, nullable=True)
    call_type = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    json_data = Column(Text, nullable=True)


class MethodMetricsModel(Base):
    __tablename__ = "method_metrics"
    
    method_id = Column(String, primary_key=True)
    run_id = Column(Integer, primary_key=True)
    project_slug = Column(String, nullable=True)
    bottleneck_score = Column(Float, nullable=True)
    betweenness_centrality = Column(Float, nullable=True)
    pagerank = Column(Float, nullable=True)
    community_id = Column(Integer, nullable=True)
    blast_radius = Column(Integer, nullable=True)
    json_data = Column(Text, nullable=True)


class AuxiliaryDataModel(Base):
    __tablename__ = "auxiliary_data"
    
    run_id = Column(Integer, primary_key=True)
    project_slug = Column(String, nullable=True)
    class_json = Column(Text, nullable=True)
    module_json = Column(Text, nullable=True)
    import_json = Column(Text, nullable=True)
    inheritance_json = Column(Text, nullable=True)


class GitRepoProfileModel(Base):
    """Repository-level aggregate health metrics."""
    __tablename__ = "git_repo_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_slug = Column(String, nullable=False, unique=True)
    repo_url = Column(String, nullable=False)
    analyzed_at = Column(String, nullable=False)

    # Repository Health
    total_commits = Column(Integer, default=0)
    total_contributors = Column(Integer, default=0)
    active_contributors_90d = Column(Integer, default=0)
    bus_factor = Column(Integer, default=0)        # contributors for 80% of commits
    first_commit_date = Column(String, nullable=True)
    last_commit_date = Column(String, nullable=True)
    days_since_last_commit = Column(Integer, default=0)
    
    # Activity Window (configurable, e.g. 365 days)
    analysis_window_days = Column(Integer, default=365)
    commits_in_window = Column(Integer, default=0)
    
    # Serialized JSON for richer data
    monthly_commit_series = Column(Text, nullable=True)   # JSON: [{month, count}]
    top_contributors_json = Column(Text, nullable=True)   # JSON: [{name, commits, pct}]


class GitFileChurnModel(Base):
    """Per-file churn metrics extracted from git log."""
    __tablename__ = "git_file_churn"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("git_repo_profiles.id"), nullable=False)
    project_slug = Column(String, nullable=False, index=True)

    file_path = Column(String, nullable=False)
    commits = Column(Integer, default=0)
    author_count = Column(Integer, default=0)
    last_modified = Column(String, nullable=True)
    top_authors_json = Column(Text, nullable=True)  # JSON: [{name, commits}]
