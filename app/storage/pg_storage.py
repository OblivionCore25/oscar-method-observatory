import json
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker

from ..models.analysis_result import AnalysisResult, AnalysisMeta, MethodMetrics
from ..models.method_node import MethodNode, ClassNode, ModuleNode
from ..models.call_edge import CallEdge, ImportEdge, InheritanceEdge

from .models import (
    Base,
    AnalysisRunModel,
    MethodNodeModel,
    CallEdgeModel,
    MethodMetricsModel,
    AuxiliaryDataModel
)

class PgStorage:
    def __init__(self, database_url: str):
        self._engine = create_engine(database_url, pool_pre_ping=True)
        Base.metadata.create_all(self._engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)

    def save(self, project_slug: str, result: AnalysisResult) -> None:
        with self.SessionLocal() as session:
            try:
                # 1. Clear older runs
                session.execute(delete(AnalysisRunModel).where(AnalysisRunModel.project_slug == project_slug))
                session.execute(delete(MethodNodeModel).where(MethodNodeModel.project_slug == project_slug))
                session.execute(delete(CallEdgeModel).where(CallEdgeModel.project_slug == project_slug))
                session.execute(delete(MethodMetricsModel).where(MethodMetricsModel.project_slug == project_slug))
                session.execute(delete(AuxiliaryDataModel).where(AuxiliaryDataModel.project_slug == project_slug))
                session.commit()

                # 2. Insert Run Header
                run = AnalysisRunModel(
                    project_slug=project_slug,
                    analyzed_at=result.meta.analyzed_at.isoformat(),
                    meta_json=result.meta.model_dump_json()
                )
                session.add(run)
                session.commit() # Commit to get run.id

                # 3. Insert Methods
                seen_methods = set()
                deduped_methods = []
                for m in result.methods:
                    if m.id not in seen_methods:
                        seen_methods.add(m.id)
                        deduped_methods.append(
                            MethodNodeModel(
                                id=m.id,
                                run_id=run.id,
                                project_slug=project_slug,
                                name=m.name,
                                module=m.module,
                                class_name=m.class_name,
                                complexity=m.complexity,
                                loc=m.loc,
                                json_data=m.model_dump_json()
                            )
                        )
                session.bulk_save_objects(deduped_methods)

                # 4. Insert Calls
                session.bulk_save_objects([
                    CallEdgeModel(
                        run_id=run.id,
                        project_slug=project_slug,
                        source_id=c.source_id,
                        target_id=c.target_id,
                        call_type=c.call_type,
                        confidence=c.confidence,
                        json_data=c.model_dump_json()
                    ) for c in result.calls
                ])

                # 5. Insert Metrics
                seen_metrics = set()
                deduped_metrics = []
                for mx in result.metrics:
                    if mx.method_id not in seen_metrics:
                        seen_metrics.add(mx.method_id)
                        deduped_metrics.append(
                            MethodMetricsModel(
                                method_id=mx.method_id,
                                run_id=run.id,
                                project_slug=project_slug,
                                bottleneck_score=mx.bottleneck_score,
                                betweenness_centrality=mx.betweenness_centrality,
                                pagerank=mx.pagerank,
                                community_id=mx.community_id,
                                blast_radius=mx.blast_radius,
                                json_data=mx.model_dump_json()
                            )
                        )
                session.bulk_save_objects(deduped_metrics)

                # 6. Insert Auxiliary
                session.add(
                    AuxiliaryDataModel(
                        run_id=run.id,
                        project_slug=project_slug,
                        class_json=json.dumps([c.model_dump(mode="json") for c in result.classes]),
                        module_json=json.dumps([m.model_dump(mode="json") for m in result.modules]),
                        import_json=json.dumps([i.model_dump(mode="json") for i in result.imports]),
                        inheritance_json=json.dumps([i.model_dump(mode="json") for i in result.inheritance]),
                    )
                )

                session.commit()
            except Exception:
                session.rollback()
                raise

    def load(self, project_slug: str) -> AnalysisResult | None:
        with self.SessionLocal() as session:
            run = session.execute(
                select(AnalysisRunModel)
                .where(AnalysisRunModel.project_slug == project_slug)
                .order_by(AnalysisRunModel.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            
            if not run:
                return None
            
            run_id = run.id
            meta = AnalysisMeta(**json.loads(run.meta_json))
            
            methods_rows = session.execute(
                select(MethodNodeModel.json_data).where(MethodNodeModel.run_id == run_id)
            ).scalars().all()
            methods = [MethodNode(**json.loads(row)) for row in methods_rows]
            
            calls_rows = session.execute(
                select(CallEdgeModel.json_data).where(CallEdgeModel.run_id == run_id)
            ).scalars().all()
            calls = [CallEdge(**json.loads(row)) for row in calls_rows]
            
            metrics_rows = session.execute(
                select(MethodMetricsModel.json_data).where(MethodMetricsModel.run_id == run_id)
            ).scalars().all()
            metrics = [MethodMetrics(**json.loads(row)) for row in metrics_rows]
            
            aux = session.execute(
                select(AuxiliaryDataModel).where(AuxiliaryDataModel.run_id == run_id)
            ).scalar_one_or_none()
            
            if not aux:
                return None
                
            classes = [ClassNode(**c) for c in json.loads(aux.class_json or "[]")]
            modules = [ModuleNode(**m) for m in json.loads(aux.module_json or "[]")]
            imports = [ImportEdge(**i) for i in json.loads(aux.import_json or "[]")]
            inheritance = [InheritanceEdge(**i) for i in json.loads(aux.inheritance_json or "[]")]

            return AnalysisResult(
                meta=meta,
                methods=methods,
                classes=classes,
                modules=modules,
                calls=calls,
                imports=imports,
                inheritance=inheritance,
                metrics=metrics
            )

    def list_projects(self) -> list[str]:
        with self.SessionLocal() as session:
            rows = session.execute(select(AnalysisRunModel.project_slug).distinct()).scalars().all()
            return list(rows)
