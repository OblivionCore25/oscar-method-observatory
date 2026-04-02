import os
import pytest
from pathlib import Path
from app.services.analysis_service import AnalysisService

@pytest.fixture
def temp_data_dir(tmp_path):
    return tmp_path / "data"

def test_analysis_service_simple_project(temp_data_dir):
    service = AnalysisService(data_directory=temp_data_dir)
    
    # Get path to the fixtures directory
    tests_dir = Path(__file__).parent
    project_path = str(tests_dir / "fixtures" / "simple_project")
    
    result = service.analyze(project_path=project_path, project_slug="simple_project")
    
    assert result.meta.project_slug == "simple_project"
    assert result.meta.method_count == 2  # main, process_data
    
    method_names = {m.name for m in result.methods}
    assert "main" in method_names
    assert "process_data" in method_names
    
    # Check metrics existence
    assert len(result.metrics) == 2
