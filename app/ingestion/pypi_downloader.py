import httpx
import tarfile
import zipfile
import shutil
from pathlib import Path
from tempfile import TemporaryFile

def download_and_extract_pypi(package_name: str, download_dir: Path, version: str | None = None) -> Path:
    """
    Fetches the PyPI JSON metadata, finds the source dist (.tar.gz) for the
    specified version (or the latest if not specified), downloads and extracts it,
    and returns the path to the extracted source directory.
    """
    # Use version-specific endpoint if a version is given
    if version:
        url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    else:
        url = f"https://pypi.org/pypi/{package_name}/json"
    
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        # Determine the version we're downloading
        resolved_version = data["info"]["version"]
        urls = data.get("urls") or data["releases"].get(resolved_version, [])
        
        bdist_url = None
        sdist_url = None
        for u in urls:
            if u["packagetype"] == "bdist_wheel" and u["url"].endswith(".whl"):
                bdist_url = u["url"]
            elif u["packagetype"] == "sdist" and u["url"].endswith(".tar.gz"):
                sdist_url = u["url"]
                
        # Prefer sdist over wheel: wheels strip source code for many packages
        # (e.g. apache-airflow ships a metadata-only wheel), while sdist
        # always contains the full .py source tree needed for AST analysis.
        target_url = sdist_url or bdist_url
        if not target_url:
            raise ValueError(f"No valid distribution (.whl or .tar.gz) found for {package_name} v{resolved_version}")

        # Ensure download parent dir exists
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # We will extract to downloading_dir / package_name_version
        target_dir = download_dir / f"{package_name}_{resolved_version}"
        
        # Clear it if it already exists from a previous failed run
        if target_dir.exists():
            shutil.rmtree(target_dir)
            
        target_dir.mkdir(parents=True)
        
        print(f"Downloading {package_name} v{resolved_version} from {target_url}...")
        
        with TemporaryFile() as tf:
            with client.stream("GET", target_url) as r:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    tf.write(chunk)
            
            tf.seek(0)
            print(f"Extracting to {target_dir}...")
            if target_url.endswith(".whl"):
                with zipfile.ZipFile(tf, "r") as z:
                    z.extractall(target_dir)
            else:
                with tarfile.open(fileobj=tf, mode="r:gz") as tar:
                    tar.extractall(path=target_dir, filter='data')

        # Find the actual source root inside the target_dir.
        # For sdist (.tar.gz): typically a single top-level dir  (e.g. requests-2.31.0/)
        # For wheel (.whl):    multiple dirs — package code + .dist-info + optional .data
        extracted_items = list(target_dir.iterdir())
        
        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            # sdist case: single extracted directory
            source_root = extracted_items[0]
        elif target_url.endswith(".whl"):
            # Wheel case: filter out metadata dirs to find the actual Python package
            source_dirs = [
                d for d in extracted_items
                if d.is_dir()
                and not d.name.endswith(".dist-info")
                and not d.name.endswith(".data")
            ]
            if len(source_dirs) == 1:
                source_root = source_dirs[0]
            elif source_dirs:
                # Multiple source dirs: use the full extraction root so all get scanned
                source_root = target_dir
            else:
                # No source dirs (metadata-only wheel): return target_dir, analyzer will find 0 methods
                source_root = target_dir
        else:
            source_root = target_dir
            
        return source_root

