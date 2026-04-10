import os
import json
import re
from pathlib import Path

def extract_dependencies(project_path: Path, ecosystem: str) -> set[str]:
    """
    Extracts declared dependencies from project manifests to feed the external classifier.
    Returns a set of dependency name roots.
    """
    deps = set()
    
    if ecosystem.lower() == "npm":
        pkg_json = project_path / "package.json"
        if pkg_json.exists():
            try:
                with open(pkg_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "dependencies" in data:
                        deps.update(data["dependencies"].keys())
                    if "devDependencies" in data:
                        deps.update(data["devDependencies"].keys())
                    if "peerDependencies" in data:
                        deps.update(data["peerDependencies"].keys())
            except Exception:
                pass
                
    elif ecosystem.lower() == "pypi":
        # pyproject.toml
        pyproject = project_path / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Basic regex for dependencies list
                deps_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if deps_match:
                    for line in deps_match.group(1).split(','):
                        line = line.strip().strip('"').strip("'")
                        if line and not line.startswith('#'):
                            # clean up version specs (e.g. Flask>=2.0)
                            pkg_name = re.split(r'[><=~!\[]', line)[0].strip()
                            if pkg_name:
                                deps.add(pkg_name)
            except Exception:
                pass
        
        # requirements.txt
        reqs = project_path / "requirements.txt"
        if reqs.exists():
            try:
                with open(reqs, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            pkg_name = re.split(r'[><=~!\[]', line)[0].strip()
                            if pkg_name:
                                deps.add(pkg_name)
            except Exception:
                pass

        # setup.py
        setup = project_path / "setup.py"
        if setup.exists():
            try:
                with open(setup, 'r', encoding='utf-8') as f:
                    content = f.read()
                # matches install_requires=['pkg1', ...]
                m = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if m:
                    for line in m.group(1).split(','):
                        line = line.strip().strip('"').strip("'")
                        if line and not line.startswith('#'):
                            pkg_name = re.split(r'[><=~!\[]', line)[0].strip()
                            if pkg_name:
                                deps.add(pkg_name)
            except Exception:
                pass
                
        # setup.cfg
        setup_cfg = project_path / "setup.cfg"
        if setup_cfg.exists():
            try:
                with open(setup_cfg, 'r', encoding='utf-8') as f:
                    in_install_requires = False
                    for line in f:
                        line = line.strip()
                        if line.startswith('install_requires'):
                            in_install_requires = True
                            if '=' in line:
                                val = line.split('=')[1].strip()
                                if val:
                                    pkg_name = re.split(r'[><=~!\[]', val)[0].strip()
                                    if pkg_name: deps.add(pkg_name)
                        elif in_install_requires:
                            if line.startswith('[') and line.endswith(']'):
                                in_install_requires = False
                            elif line and not line.startswith('#'):
                                pkg_name = re.split(r'[><=~!\[]', line)[0].strip()
                                if pkg_name: deps.add(pkg_name)
            except Exception:
                pass

    # Clean up deps
    if ecosystem.lower() == "pypi":
        # Python dependencies often use hyphens but modules use underscores. 
        # Add both to be safe. Also some common aliases.
        normalized = set()
        for d in deps:
            lower_d = d.lower()
            normalized.add(lower_d)
            normalized.add(lower_d.replace('-', '_'))
            
            # Common module aliases for typing
            if lower_d == 'typing-extensions' or lower_d == 'typing_extensions':
                normalized.add('typing_extensions')
        
        # Add some extremely common implicit frameworks or aliases
        # If Flask is listed, add werkzeug, jinja2, markupsafe, click etc 
        # because they are transitive but used as primary imports
        if 'flask' in normalized:
            normalized.update(['werkzeug', 'jinja2', 'markupsafe', 'click', 'itsdangerous'])
            
        deps = normalized
        
    elif ecosystem.lower() == "npm":
        # Remove scope for scoped packages (e.g. @babel/core -> core) if needed, 
        # but Node requires keeping the scope.
        # So we keep exact pkg names. We also add the un-scoped name just in case
        normalized = set()
        for d in deps:
            normalized.add(d)
            if d.startswith('@') and '/' in d:
                normalized.add(d.split('/')[1])
        deps = normalized

    return deps
