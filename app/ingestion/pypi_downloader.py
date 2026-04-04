import httpx
import tarfile
import shutil
from pathlib import Path
from tempfile import TemporaryFile

def download_and_extract_pypi(package_name: str, download_dir: Path) -> Path:
    """
    Fetches the PyPI JSON metadata, finds the latest source dist (.tar.gz),
    downloads it to a temporary location, extracts it, and returns the path to the 
    extracted source directory.
    """
    url = f"https://pypi.org/pypi/{package_name}/json"
    
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        # Get the latest version's urls
        latest_version = data["info"]["version"]
        urls = data["releases"].get(latest_version, [])
        
        sdist_url = None
        for u in urls:
            if u["packagetype"] == "sdist" and u["url"].endswith(".tar.gz"):
                sdist_url = u["url"]
                break
                
        if not sdist_url:
            raise ValueError(f"No source distribution (.tar.gz) found for {package_name} v{latest_version}")

        # Ensure download parent dir exists
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # We will extract to downloading_dir / package_name_version
        target_dir = download_dir / f"{package_name}_{latest_version}"
        
        # Clear it if it already exists from a previous failed run
        if target_dir.exists():
            shutil.rmtree(target_dir)
            
        target_dir.mkdir(parents=True)
        
        print(f"Downloading {package_name} from {sdist_url}...")
        
        with TemporaryFile() as tf:
            with client.stream("GET", sdist_url) as r:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    tf.write(chunk)
            
            tf.seek(0)
            print(f"Extracting to {target_dir}...")
            with tarfile.open(fileobj=tf, mode="r:gz") as tar:
                # The tar usually contains a single top-level folder (e.g. requests-2.31.0/)
                # extractall handles this fine, we just return the target_dir
                
                # To be safe from arbitrary paths in tarballs
                # modern python (3.12+) supports filter='data'
                tar.extractall(path=target_dir, filter='data')

        # Find the actual source root inside the target_dir (e.g. target_dir/requests-2.31.0)
        # We assume there's one top-level directory extracted.
        extracted_items = list(target_dir.iterdir())
        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            source_root = extracted_items[0]
        else:
            source_root = target_dir
            
        return source_root
