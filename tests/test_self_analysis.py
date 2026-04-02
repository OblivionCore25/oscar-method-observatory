import os
import pytest
from pathlib import Path
from app.services.analysis_service import AnalysisService

@pytest.fixture
def temp_data_dir(tmp_path):
    return tmp_path / "data"

def test_self_analysis_oscar_backend(temp_data_dir):
    service = AnalysisService(data_directory=temp_data_dir)
    
    # Analyze the entire backend application, up one level relative to the tests dir
    backend_dir = Path(__file__).parent.parent
    
    result = service.analyze(project_path=str(backend_dir), project_slug="oscar-self-analysis", exclude_tests=True)
    
    assert result.meta.project_slug == "oscar-self-analysis"
    assert result.meta.method_count > 10
    
    # In Phase 1, all 3rd party framework calls (FastAPI, Pydantic) are counted as "unresolved" 
    # since they are not in the local method map. A 10%+ rate indicates local calls are still mapping correctly.
    assert result.meta.resolution_rate > 0.1
    
    # Check for method ID collisions
    method_ids = [m.id for m in result.methods]
    assert len(method_ids) == len(set(method_ids))
