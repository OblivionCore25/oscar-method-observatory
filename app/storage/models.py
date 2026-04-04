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
