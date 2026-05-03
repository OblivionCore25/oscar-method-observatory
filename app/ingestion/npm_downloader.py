from __future__ import annotations
import httpx
import tarfile
import shutil
from pathlib import Path
from tempfile import TemporaryFile

_GIT_HOSTS = ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org", "sr.ht")


def _normalise_git_url(url: str) -> str | None:
    """Convert various git URL formats to a plain HTTPS clone URL."""
    if not url:
        return None
        
    url = url.strip().rstrip("/")
    
    # Strip any commit hash fragments (#...)
    import re
    url = re.sub(r'#.*$', '', url)
    
    # Handle git+ prefixes
    if url.startswith("git+"):
        url = url[4:]
        
    # Handle various protocol transformations to pure HTTPS
    if url.startswith("git://"):
        url = url.replace("git://", "https://", 1)
    elif url.startswith("git@"):
        url = url.replace(":", "/", 1).replace("git@", "https://", 1)
    elif url.startswith("ssh://git@"):
        url = url.replace("ssh://git@", "https://", 1)

    if not any(host in url for host in _GIT_HOSTS):
        return None
        
    # Strip monorepo subdirectory paths like /tree/master/packages/foo
    if "github.com" in url or "gitlab.com" in url:
        url = re.sub(r'/(tree|blob)/.*$', '', url)
        
    if not url.endswith(".git"):
        url = url + ".git"
    return url


def resolve_repo_url_npm(package_name: str) -> str | None:
    """
    Query the npm registry API and extract the source repository URL.
    Returns a normalised HTTPS clone URL, or None if not found.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"https://registry.npmjs.org/{package_name}")
            if resp.status_code != 200:
                return None
            data = resp.json()
            latest = data.get("dist-tags", {}).get("latest")
            if not latest:
                return None
            version_data = data.get("versions", {}).get(latest, {})
            # Try version-level repository first (most specific), then package-level
            for source in (version_data, data):
                repo = source.get("repository")
                if isinstance(repo, dict):
                    url = _normalise_git_url(repo.get("url", ""))
                    if url:
                        return url
                elif isinstance(repo, str):
                    url = _normalise_git_url(repo)
                    if url:
                        return url
            # Some packages put it in bugs.url or homepage as a fallback
            homepage = _normalise_git_url(data.get("homepage", ""))
            if homepage:
                return homepage
    except Exception:
        pass
    return None

def download_and_extract_npm(package_name: str, download_dir: Path) -> Path:
    """
    Fetches the NPM JSON metadata, finds the latest source dist (.tgz),
    downloads it to a temporary location, extracts it, and returns the path to the 
    extracted source directory.
    
    Handles scoped packages (e.g. '@babel/core') by normalizing the name 
    for the download dir (e.g. 'babel__core').
    """
    # npm api needs URL encoding for scoped packages, e.g. @babel/core -> %40babel%2Fcore
    # But usually just /@babel/core works on registry.npmjs.org
    url = f"https://registry.npmjs.org/{package_name}"
    
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        # Get the latest version's urls
        latest_version = data.get("dist-tags", {}).get("latest")
        if not latest_version:
             raise ValueError(f"No 'latest' dist-tag found for {package_name}")
             
        version_data = data.get("versions", {}).get(latest_version)
        if not version_data:
            raise ValueError(f"Version {latest_version} not found in versions dict")

        tarball_url = version_data.get("dist", {}).get("tarball")
        
        if not tarball_url:
            raise ValueError(f"No tarball found for {package_name} v{latest_version}")

        # Ensure download parent dir exists
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Normalize scoped package name for directory creation
        normalized_name = package_name.replace("@", "").replace("/", "__")
        
        target_dir = download_dir / f"{normalized_name}_{latest_version}"
        
        # Clear it if it already exists from a previous failed run
        if target_dir.exists():
            shutil.rmtree(target_dir)
            
        target_dir.mkdir(parents=True)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Downloading {package_name} from {tarball_url}...")
        
        with TemporaryFile() as tf:
            with client.stream("GET", tarball_url) as r:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    tf.write(chunk)
            
            tf.seek(0)
            logger.info(f"Extracting to {target_dir}...")
            with tarfile.open(fileobj=tf, mode="r:gz") as tar:
                # `tar.extractall` with `filter='data'` (Python 3.12+) or just default
                if hasattr(tarfile, 'data_filter'):
                    tar.extractall(path=target_dir, filter='data')
                else:
                    tar.extractall(path=target_dir)

        # Find the actual source root inside the target_dir (usually a 'package/' dir)
        extracted_items = list(target_dir.iterdir())
        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            source_root = extracted_items[0]
        else:
            source_root = target_dir
            
        return source_root
