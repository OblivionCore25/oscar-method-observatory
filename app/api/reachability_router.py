from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from pydantic import BaseModel

from app.analysis.reachability import ReachabilityAnalyzer, ReachabilityResult
from app.services.analysis_service import AnalysisService
from app.api.router import get_service

router = APIRouter(prefix="/reachability", tags=["reachability"])

class ReachabilityResponse(BaseModel):
    results: List[ReachabilityResult]
    entry_points_found: int
    total_methods: int
    resolution_rate: float

@router.get("/{slug}", response_model=ReachabilityResponse)
def get_reachability(
    slug: str, 
    functions: str = Query(..., description="Comma separated function names"),
    service: AnalysisService = Depends(get_service)
):
    """
    Evaluates whether specific vulnerable target functions are structurally reachable 
    from any public API entry paths located inside the method-level call graph.
    """
    result = service.load(slug)
    if not result:
        raise HTTPException(status_code=404, detail="Project AST graph not found.")
        
    target_functions = [f.strip() for f in functions.split(",") if f.strip()]
    if not target_functions:
        raise HTTPException(status_code=400, detail="No function names provided.")
        
    analyzer = ReachabilityAnalyzer()
    rs = analyzer.check_reachability(target_functions, result)
    entry_points = analyzer.find_entry_points(
        result.methods,
        result.calls,
        modules=result.modules,
        imports=result.imports,
        classes=result.classes,
    )
    
    return ReachabilityResponse(
        results=rs,
        entry_points_found=len(entry_points),
        total_methods=len(result.methods),
        resolution_rate=result.meta.resolution_rate
    )
