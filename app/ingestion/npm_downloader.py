import httpx
import tarfile
import shutil
from pathlib import Path
from tempfile import TemporaryFile

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
        
        print(f"Downloading {package_name} from {tarball_url}...")
        
        with TemporaryFile() as tf:
            with client.stream("GET", tarball_url) as r:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    tf.write(chunk)
            
            tf.seek(0)
            print(f"Extracting to {target_dir}...")
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
