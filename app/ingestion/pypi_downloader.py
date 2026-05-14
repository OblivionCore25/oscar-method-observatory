from __future__ import annotations
import httpx
import tarfile
import zipfile
import shutil
from pathlib import Path
from tempfile import TemporaryFile

# Ordered preference of project_url keys that tend to carry the source repo
_PYPI_REPO_URL_KEYS = ["Source", "Repository", "Code", "GitHub", "Source Code", "Homepage"]
_GIT_HOSTS = ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org", "sr.ht")


def _normalise_git_url(url: str) -> str | None:
    """Convert various git URL formats to a plain HTTPS clone URL."""
    if not url:
        return None
    url = url.strip().rstrip("/")
    # Convert SSH git@ URLs → https
    if url.startswith("git@"):
        url = url.replace(":", "/", 1).replace("git@", "https://", 1)
    # Strip git+ prefix
    if url.startswith("git+"):
        url = url[4:]
    # Must be from a known git host
    if not any(host in url for host in _GIT_HOSTS):
        return None
    # Ensure .git suffix for cloning
    if not url.endswith(".git"):
        url = url + ".git"
    return url


def resolve_repo_url_pypi(package_name: str, version: str | None = None) -> str | None:
    """
    Query the PyPI JSON API and extract the source repository URL.
    Returns a normalised HTTPS clone URL, or None if not found.
    """
    def _extract_from_data(data: dict) -> str | None:
        project_urls: dict = data.get("info", {}).get("project_urls") or {}
        for key in _PYPI_REPO_URL_KEYS:
            url = _normalise_git_url(project_urls.get(key, ""))
            if url:
                return url
        for url in project_urls.values():
            norm = _normalise_git_url(url or "")
            if norm:
                return norm
        return None    

    candidates = []
    if version:
        candidates.append(f"https://pypi.org/pypi/{package_name}/{version}/json")
    # Always include the unversioned endpoint as a fallback — old releases often lack project_urls
    candidates.append(f"https://pypi.org/pypi/{package_name}/json")

    try:
        with httpx.Client(timeout=10.0) as client:
            for api_url in candidates:
                resp = client.get(api_url)
                if resp.status_code != 200:
                    continue
                result = _extract_from_data(resp.json())
                if result:
                    return result
    except Exception:
        pass
    return None

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
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Downloading {package_name} v{resolved_version} from {target_url}...")
        
        with TemporaryFile() as tf:
            with client.stream("GET", target_url) as r:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    tf.write(chunk)
            
            tf.seek(0)
            logger.info(f"Extracting to {target_dir}...")
            if target_url.endswith(".whl"):
                with zipfile.ZipFile(tf, "r") as z:
                    z.extractall(target_dir)
            else:
                with tarfile.open(fileobj=tf, mode="r:gz") as tar:
                    # filter='data' requires Python 3.12+; use a compat shim
                    import sys
                    if sys.version_info >= (3, 12):
                        tar.extractall(path=target_dir, filter='data')
                    else:
                        # Manual safety check: skip absolute paths and parent traversal
                        safe_members = [
                            m for m in tar.getmembers()
                            if not m.name.startswith('/') and '..' not in m.name
                        ]
                        tar.extractall(path=target_dir, members=safe_members)

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

