import asyncio
from app.services.analysis_service import AnalysisService
from app.api.router import auto_ingest_package
from pathlib import Path
from app.config import settings

def test():
    service = AnalysisService(
        data_directory=Path(settings.data_directory),
        oscar_version=settings.app_version,
        max_file_size_kb=settings.method_max_file_size_kb
    )
    for pkg in ["@jest/core", "@babel/core", "express"]:
        print(f"Re-ingesting {pkg}...")
        try:
            asyncio.run(auto_ingest_package("npm", pkg, service))
        except Exception as e:
            print("ERROR", str(e))
            
if __name__ == "__main__":
    test()
