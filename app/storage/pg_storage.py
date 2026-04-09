import json
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker

from ..models.analysis_result import AnalysisResult, AnalysisMeta, MethodMetrics
from ..models.method_node import MethodNode, ClassNode, ModuleNode
from ..models.call_edge import CallEdge, ImportEdge, InheritanceEdge

from ..models.git_profile import GitRepoHealth, GitFileChurn, GitAnalysisResult

from .models import (
    Base,
    AnalysisRunModel,
    MethodNodeModel,
    CallEdgeModel,
    MethodMetricsModel,
    AuxiliaryDataModel,
    GitRepoProfileModel,
    GitFileChurnModel
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

    def list_projects(self) -> list[dict]:
        with self.SessionLocal() as session:
            # PostgreSQL requires DISTINCT ON or GROUP BY for max/distinct with other columns.
            # We'll use a simple DISTINCT (select project_slug) but to get meta_json we must group or query.
            # For simplicity, let's fetch all runs and distinct in python, there aren't that many yet.
            rows = session.execute(
                select(AnalysisRunModel.project_slug, AnalysisRunModel.meta_json)
                .order_by(AnalysisRunModel.id.desc())
            ).all()
            
            seen = set()
            out = []
            for slug, meta_json in rows:
                if slug in seen:
                    continue
                seen.add(slug)
                meta = json.loads(meta_json)
                if meta.get("method_count", 0) == 0:
                    continue
                ecosystem = "npm" if meta.get("analysis_approach") == "tree_sitter_static" else "pypi"
                out.append({"slug": slug, "ecosystem": ecosystem})
            return out

    def save_git_profile(self, result: GitAnalysisResult) -> None:
        with self.SessionLocal() as session:
            try:
                session.execute(delete(GitRepoProfileModel).where(GitRepoProfileModel.project_slug == result.health.project_slug))
                session.execute(delete(GitFileChurnModel).where(GitFileChurnModel.project_slug == result.health.project_slug))
                session.commit()

                h = result.health
                profile = GitRepoProfileModel(
                    project_slug=h.project_slug,
                    repo_url=h.repo_url,
                    analyzed_at=h.analyzed_at.isoformat(),
                    total_commits=h.total_commits,
                    total_contributors=h.total_contributors,
                    active_contributors_90d=h.active_contributors_90d,
                    bus_factor=h.bus_factor,
                    first_commit_date=h.first_commit_date,
                    last_commit_date=h.last_commit_date,
                    days_since_last_commit=h.days_since_last_commit,
                    analysis_window_days=h.analysis_window_days,
                    commits_in_window=h.commits_in_window,
                    monthly_commit_series=json.dumps(h.monthly_commit_series),
                    top_contributors_json=json.dumps(h.top_contributors)
                )
                session.add(profile)
                session.commit()

                churn_models = []
                for c in result.files:
                    churn_models.append(
                        GitFileChurnModel(
                            profile_id=profile.id,
                            project_slug=h.project_slug,
                            file_path=c.file_path,
                            commits=c.commits,
                            author_count=c.author_count,
                            last_modified=c.last_modified,
                            top_authors_json=json.dumps(c.top_authors)
                        )
                    )
                session.bulk_save_objects(churn_models)
                session.commit()
            except Exception:
                session.rollback()
                raise

    def load_git_profile(self, project_slug: str) -> GitRepoHealth | None:
        with self.SessionLocal() as session:
            profile = session.execute(
                select(GitRepoProfileModel)
                .where(GitRepoProfileModel.project_slug == project_slug)
            ).scalar_one_or_none()
            
            if not profile:
                return None
                
            from datetime import datetime
            return GitRepoHealth(
                project_slug=profile.project_slug,
                repo_url=profile.repo_url,
                analyzed_at=datetime.fromisoformat(profile.analyzed_at),
                total_commits=profile.total_commits,
                total_contributors=profile.total_contributors,
                active_contributors_90d=profile.active_contributors_90d,
                bus_factor=profile.bus_factor,
                first_commit_date=profile.first_commit_date,
                last_commit_date=profile.last_commit_date,
                days_since_last_commit=profile.days_since_last_commit,
                analysis_window_days=profile.analysis_window_days,
                commits_in_window=profile.commits_in_window,
                monthly_commit_series=json.loads(profile.monthly_commit_series or "[]"),
                top_contributors=json.loads(profile.top_contributors_json or "[]")
            )

    def load_git_file_churn(self, project_slug: str) -> list[GitFileChurn]:
        with self.SessionLocal() as session:
            rows = session.execute(
                select(GitFileChurnModel)
                .where(GitFileChurnModel.project_slug == project_slug)
            ).scalars().all()
            
            results = []
            for row in rows:
                results.append(GitFileChurn(
                    file_path=row.file_path,
                    commits=row.commits,
                    author_count=row.author_count,
                    last_modified=row.last_modified,
                    top_authors=json.loads(row.top_authors_json or "[]")
                ))
            return results

    def load_git_file_churn_map(self, project_slug: str) -> dict[str, GitFileChurn]:
        churns = self.load_git_file_churn(project_slug)
        return {c.file_path: c for c in churns}
