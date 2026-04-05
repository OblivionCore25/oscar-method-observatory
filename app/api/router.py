from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from pathlib import Path
from ..services.analysis_service import AnalysisService
from ..models.analysis_result import AnalysisResult, AnalysisMeta, MethodMetrics

router = APIRouter(prefix="/methods", tags=["Method Observatory"])


# ── Request/Response schemas ──────────────────────────────────────────────── #

class AnalyzeRequest(BaseModel):
    project_path: str              # Absolute path on the analysis server's filesystem
    project_slug: str              # Short identifier used in storage and URLs
    exclude_tests: bool = False


class AnalyzeSummaryResponse(BaseModel):
    project_slug: str
    meta: AnalysisMeta
    top_risk: list[MethodMetrics]  # Top 10 by bottleneck score

class IngestResponse(BaseModel):
    project_slug: str
    message: str
    is_meta_package: bool = False
    resolved_core_slug: str | None = None
    meta_dependencies: list[str] = []


class MethodDetailResponse(BaseModel):
    method: dict                   # Full MethodNode serialized
    metrics: MethodMetrics
    callers: list[dict]            # List of {method_node, edge_info}
    callees: list[dict]            # List of {method_node, edge_info}


# ── Dependency injection ──────────────────────────────────────────────────── #

def get_service() -> AnalysisService:
    from app.config import settings
    return AnalysisService(
        data_directory=Path(settings.data_directory),
        oscar_version=settings.app_version,
        max_file_size_kb=settings.method_max_file_size_kb
    )


# ── Endpoints ─────────────────────────────────────────────────────────────── #

@router.post("/analyze", response_model=AnalyzeSummaryResponse)
async def analyze_project(request: AnalyzeRequest, service: AnalysisService = Depends(get_service)):
    """
    Trigger analysis of a Python project directory.
    Runs the full ingestion → AST parsing → call resolution → metrics pipeline.
    Returns a summary with top-risk methods on completion.
    """
    try:
        result = service.analyze(
            project_path=request.project_path,
            project_slug=request.project_slug,
            exclude_tests=request.exclude_tests,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    top_risk = sorted(result.metrics, key=lambda m: m.bottleneck_score, reverse=True)[:10]
    return AnalyzeSummaryResponse(project_slug=result.meta.project_slug, meta=result.meta, top_risk=top_risk)



@router.post("/ingest/{ecosystem}/{package_name}", response_model=IngestResponse)
async def auto_ingest_package(
    ecosystem: str,
    package_name: str,
    service: AnalysisService = Depends(get_service)
):
    """
    Downloads package source code (if PyPI) and executes AST analysis, 
    deleting the source files immediately after success.
    """
    if ecosystem.lower() == "npm":
        # Graceful placeholder for future NPM AST parsing
        return IngestResponse(
            project_slug=package_name,
            message="AST Parsing for NPM is not yet implemented. Returning placeholder response."
        )
        
    if ecosystem.lower() != "pypi":
        raise HTTPException(status_code=400, detail="Only PyPI ecosystem is currently supported for auto-ingestion.")
        
    import shutil
    from app.config import settings
    from app.ingestion.pypi_downloader import download_and_extract_pypi
    
    download_base_dir = Path(settings.data_directory) / "downloads"
    
    try:
        source_root = download_and_extract_pypi(package_name, download_base_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PyPI package: {str(e)}")
        
    try:
        # We pass the extracted dir to the service
        # The service will overwrite any existing run in postgres automatically
        result = service.analyze(
            project_path=str(source_root),
            project_slug=package_name,
            ecosystem=ecosystem.lower(),
            exclude_tests=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Cleanup source code as requested
        target_dir = source_root
        # Handle the case where source_root was inside a parent extraction dir 
        # (e.g. downloads/flask_3.0.0/flask-3.0.0/). We want to clean the parent.
        if target_dir.parent == download_base_dir:
            shutil.rmtree(target_dir, ignore_errors=True)
        else:
            shutil.rmtree(target_dir.parent, ignore_errors=True)

    is_meta_package = False
    resolved_core_slug = None
    meta_dependencies = []

    # Meta-Package Ast Redirection Fallback
    if result.meta.method_count == 0:
        import httpx
        import re
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(f"https://pypi.org/pypi/{package_name}/json")
                if r.status_code == 200:
                    data = r.json()
                    reqs = data.get("info", {}).get("requires_dist") or []
                    
                    parsed_reqs = []
                    for req in reqs:
                        match = re.search(r'^([a-zA-Z0-9_\-]+)', req)
                        if match:
                            parsed_reqs.append(match.group(1).lower())
                            
                    if parsed_reqs:
                        is_meta_package = True
                        # Uniquify maintaining order
                        meta_dependencies = list(dict.fromkeys(parsed_reqs))
                        
                        # Heuristic Core Matching
                        candidates = [dep for dep in meta_dependencies if dep.startswith(package_name.lower()) and len(dep) > len(package_name)]
                        if candidates:
                            resolved_core_slug = sorted(candidates, key=len)[0]
                            
                            # Transitive Deep Ingest
                            source_root_core = download_and_extract_pypi(resolved_core_slug, download_base_dir)
                            try:
                                service.analyze(
                                    project_path=str(source_root_core),
                                    project_slug=resolved_core_slug,
                                    exclude_tests=True
                                )
                            except Exception:
                                pass # Provide partial degraded if transit fails
                            finally:
                                if source_root_core.parent == download_base_dir:
                                    shutil.rmtree(source_root_core, ignore_errors=True)
                                else:
                                    shutil.rmtree(source_root_core.parent, ignore_errors=True)
                                    
        except Exception as e:
            print(f"Meta-Package check failed: {e}")

    return IngestResponse(
        project_slug=package_name,
        message=f"Successfully analyzed PyPI package '{package_name}'.",
        is_meta_package=is_meta_package,
        resolved_core_slug=resolved_core_slug,
        meta_dependencies=meta_dependencies
    )



@router.get("/projects", response_model=list[str])
async def list_projects(service: AnalysisService = Depends(get_service)):
    """List all previously analyzed projects."""
    return service.list_projects()


@router.get("/{project_slug}", response_model=AnalysisMeta)
async def get_project_meta(project_slug: str, service: AnalysisService = Depends(get_service)):
    """Return analysis metadata for a project (summary statistics)."""
    result = service.load(project_slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")
    return result.meta


@router.get("/{project_slug}/top-risk", response_model=list[MethodMetrics])
async def get_top_risk(
    project_slug: str,
    limit: int = Query(default=10, ge=1, le=100),
    service: AnalysisService = Depends(get_service),
):
    """
    Return methods ranked by bottleneck score (fan_in × fan_out).
    Mirrors OSCAR's /analytics/top-risk endpoint at the method level.
    """
    result = service.load(project_slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")
    ranked = sorted(result.metrics, key=lambda m: m.bottleneck_score, reverse=True)
    return ranked[:limit]


@router.get("/{project_slug}/orphans", response_model=list[dict])
async def get_orphans(
    project_slug: str,
    service: AnalysisService = Depends(get_service),
):
    """
    Return methods with fan_in=0 (never called within the project).
    Candidates for dead code removal.
    """
    result = service.load(project_slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")

    method_map = {m.id: m for m in result.methods}
    orphans = [m for m in result.metrics if m.is_orphan]
    return [{"method": method_map[m.method_id].model_dump(), "metrics": m.model_dump()}
            for m in orphans if m.method_id in method_map]


@router.get("/{project_slug}/hotspots", response_model=list[dict])
async def get_hotspots(
    project_slug: str,
    limit: int = Query(default=20, ge=1, le=100),
    service: AnalysisService = Depends(get_service),
):
    """
    Return methods ranked by composite risk score (complexity * centrality * blast_radius).
    """
    result = service.load(project_slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")

    method_map = {m.id: m for m in result.methods}
    hotspots = []
    for m in result.metrics:
        comp = m.complexity or 1
        cent = m.betweenness_centrality or 0.0
        blast = m.blast_radius or 0
        score = comp * cent * blast
        hotspots.append({
            "method": method_map[m.method_id].model_dump() if m.method_id in method_map else None,
            "metrics": m.model_dump(),
            "composite_risk": score
        })
    
    hotspots = [h for h in hotspots if h["method"]]
    ranked = sorted(hotspots, key=lambda x: x["composite_risk"], reverse=True)
    return ranked[:limit]


@router.get("/{project_slug}/communities", response_model=dict[str, list[dict]])
async def get_communities(
    project_slug: str,
    service: AnalysisService = Depends(get_service),
):
    """
    Return methods grouped by Louvain community assignment.
    """
    result = service.load(project_slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")

    method_map = {m.id: m for m in result.methods}
    communities = {}
    for m in result.metrics:
        cid = m.community_id
        if cid is None:
            continue
        cid_str = str(cid)
        if cid_str not in communities:
            communities[cid_str] = []
        if m.method_id in method_map:
            communities[cid_str].append({
                "method": method_map[m.method_id].model_dump(),
                "metrics": m.model_dump()
            })
    return communities


@router.get("/{project_slug}/method/{method_id:path}/blast-radius", response_model=dict)
async def get_blast_radius(
    project_slug: str,
    method_id: str,
    service: AnalysisService = Depends(get_service),
):
    """
    Return the transitive closure of downstream callees for a specific method.
    """
    result = service.load(project_slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")

    import networkx as nx
    G = nx.DiGraph()
    for c in result.calls:
        if c.confidence > 0:
            G.add_edge(c.source_id, c.target_id, **c.model_dump())

    if method_id not in G:
        raise HTTPException(status_code=404, detail=f"Method '{method_id}' not found in graph")

    reachable = list(nx.descendants(G, method_id))
    
    method_map = {m.id: m.model_dump() for m in result.methods}
    metrics_map = {m.method_id: m.model_dump() for m in result.metrics}

    nodes = []
    edges = []
    
    for n in [method_id] + reachable:
        if n in method_map:
            nodes.append({**method_map[n], **metrics_map.get(n, {})})
            
    subgraph = G.subgraph([method_id] + reachable)
    for u, v, data in subgraph.edges(data=True):
        edges.append(data)

    return {
        "root": method_id,
        "node_count": len(nodes),
        "nodes": nodes,
        "edges": edges,
    }


@router.get("/{project_slug}/method/{method_id:path}", response_model=MethodDetailResponse)
async def get_method_detail(
    project_slug: str,
    method_id: str,
    service: AnalysisService = Depends(get_service),
):
    """
    Return full detail for one method: its node data, metrics, and immediate callers/callees.
    """
    result = service.load(project_slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")

    method_map = {m.id: m for m in result.methods}
    metrics_map = {m.method_id: m for m in result.metrics}

    if method_id not in method_map:
        raise HTTPException(status_code=404, detail=f"Method '{method_id}' not found")

    method = method_map[method_id]
    metrics = metrics_map.get(method_id)

    # Collect callers (edges where target == method_id)
    callers = []
    for call in result.calls:
        if call.target_id == method_id and call.source_id in method_map:
            callers.append({
                "method": method_map[call.source_id].model_dump(),
                "edge": call.model_dump(),
            })

    # Collect callees (edges where source == method_id)
    callees = []
    for call in result.calls:
        if call.source_id == method_id and call.target_id in method_map:
            callees.append({
                "method": method_map[call.target_id].model_dump(),
                "edge": call.model_dump(),
            })

    return MethodDetailResponse(
        method=method.model_dump(),
        metrics=metrics,
        callers=callers,
        callees=callees,
    )


@router.get("/{project_slug}/graph", response_model=dict)
async def export_graph(
    project_slug: str,
    format: str = Query(default="json", enum=["json", "csv"]),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    service: AnalysisService = Depends(get_service),
):
    """
    Export the full method call graph for downstream analysis (Gephi, NetworkX, etc.).
    Mirrors OSCAR's /export/{ecosystem}/graph endpoint.

    JSON format: { "project": "...", "nodes": [...], "edges": [...] }
    CSV format: source,target,call_type,confidence
    """
    result = service.load(project_slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_slug}' not found")

    method_map = {m.id: m for m in result.methods}
    metrics_map = {m.method_id: m for m in result.metrics}

    filtered_calls = [
        c for c in result.calls
        if c.confidence >= min_confidence
        and not c.target_id.startswith("unresolved:")
        and c.source_id in method_map
        and c.target_id in method_map
    ]

    if format == "csv":
        from fastapi.responses import PlainTextResponse
        lines = ["source,target,call_type,confidence"]
        for call in filtered_calls:
            lines.append(f"{call.source_id},{call.target_id},{call.call_type},{call.confidence}")
        return PlainTextResponse("\n".join(lines), media_type="text/csv")

    nodes = [
        {**method_map[mid].model_dump(), **metrics_map[mid].model_dump()}
        for mid in method_map
        if mid in metrics_map
    ]
    edges = [c.model_dump() for c in filtered_calls]

    return {
        "project": project_slug,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
