import subprocess
import os
import re
import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict
from collections import Counter

HARDENED_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",    # DONT READ GLOBAL USER CONFIG
    "GIT_CONFIG_SYSTEM": "/dev/null",    # DONT READ SYSTEM CONFIG
    "GIT_TERMINAL_PROMPT": "0",          # NEVER PROMPT FOR PASSWORD
    "GIT_ASKPASS": "echo",               # DONT USE ASKPASS PROTOCOL
}

HARDENED_GIT_FLAGS = [
    "-c", "protocol.file.allow=never",   # DISABLE LOCAL CLONES TO PREVENT LFI
    "-c", "core.symlinks=false",         # PREVENT MALICIOUS SYMLINK EXTRACTION
]

@dataclass
class FileChurn:
    commits: int
    authors: Counter
    last_modified: str | None


class GitAnalyzer:
    def clone_bare(self, repo_url: str, target_dir: Path, timeout: int = 600, force_refresh: bool = False) -> Path:
        """
        Blobless bare clone: commit graph only, no file content.
        Safe against remote code execution or symlink writes.
        """
        if (target_dir / "HEAD").exists() and not force_refresh:
            return target_dir

        if target_dir.exists():
            import shutil
            shutil.rmtree(target_dir, ignore_errors=True)

        target_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(HARDENED_GIT_ENV)
        
        cmd = [
            "git",
            *HARDENED_GIT_FLAGS,
            "clone",
            "--bare",
            repo_url,
            str(target_dir)
        ]
        
        try:
            subprocess.run(
                cmd, 
                env=env, 
                check=True, 
                timeout=timeout,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode('utf-8', errors='ignore').strip() if e.stderr else str(e)
            raise RuntimeError(f"Git clone failed: {error_msg}")
            
        return target_dir

    def extract_file_churn(self, bare_repo: Path, since_days: int = 365) -> Dict[str, FileChurn]:
        """
        Parse `git log --numstat` to get file-level churn metrics.
        Returns a dict mapping file path to FileChurn metrics.
        """
        env = os.environ.copy()
        env.update(HARDENED_GIT_ENV)
        
        since_date = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=since_days)).strftime("%Y-%m-%d")
        
        # Git log output format:
        # commit <hash>
        # Author: <name>
        # Date: <iso_date>
        # 
        # <added> <deleted> <filepath>
        
        cmd = [
            "git",
            *HARDENED_GIT_FLAGS,
            "-C", str(bare_repo),
            "log",
            f"--since={since_date}",
            "--name-only",
            "--format=commit %x1f%aN%x1f%aI", # separator: \x1f (unit separator)
            "--no-renames"
        ]
        
        result = subprocess.run(
            cmd,
            env=env,
            check=False,
            timeout=600, # Increased timeout to safely handle massive repos like Next.js
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            # Maybe the repo is empty or failed to parse
            print(f"Git log failed: {result.stderr}")
            return {}

        churn_map: Dict[str, FileChurn] = {}
        
        current_author = None
        current_date = None
        
        lines = result.stdout.splitlines()
        for line in lines:
            if not line.strip():
                continue
                
            if line.startswith("commit "):
                parts = line[7:].split("\x1f")
                if len(parts) >= 3:
                    current_author = parts[1]
                    current_date = parts[2]
                continue
                
            # --name-only outputs just the filepath on lines following the commit header
            filepath = line.strip()
            
            if filepath not in churn_map:
                churn_map[filepath] = FileChurn(commits=0, authors=Counter(), last_modified=current_date)
                
            churn = churn_map[filepath]
            churn.commits += 1
            if current_author:
                churn.authors[current_author] += 1
                
            # The first time we see a file in `git log` (which is reverse chronological),
            # that is the most recent modification.
            if not churn.last_modified and current_date:
                churn.last_modified = current_date

        return churn_map

    def extract_repo_health(self, bare_repo: Path, since_days: int = 365) -> dict:
        """
        Returns a dict of repo-level aggregate metrics.
        """
        env = os.environ.copy()
        env.update(HARDENED_GIT_ENV)
        
        # Get overall commit history with dates and authors
        cmd = [
            "git",
            *HARDENED_GIT_FLAGS,
            "-C", str(bare_repo),
            "log",
            "--format=%x1f%aN%x1f%aI" # \x1f + author_name + \x1f + author_iso_date
        ]
        
        result = subprocess.run(cmd, env=env, check=False, timeout=300, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            return {}

        lines = result.stdout.splitlines()
        
        total_commits = 0
        authors = Counter()
        first_commit_date = None
        last_commit_date = None
        
        now = datetime.datetime.now(datetime.UTC)
        window_start = now - datetime.timedelta(days=since_days)
        window_90d = now - datetime.timedelta(days=90)
        
        commits_in_window = 0
        active_authors_90d = set()
        
        # month string to count
        monthly_series_map = Counter()
        
        for line in lines:
            if not line.startswith("\x1f"):
                continue
            parts = line.split("\x1f")
            if len(parts) < 3:
                continue
                
            author = parts[1]
            date_str = parts[2]
            
            total_commits += 1
            authors[author] += 1
            
            if not last_commit_date:
                last_commit_date = date_str  # First iteration is the latest commit
            first_commit_date = date_str # Last iteration will be the earliest commit
            
            try:
                # Handle varying ISO formats from git
                clean_date_str = date_str.replace("Z", "+00:00")
                parsed_date = datetime.datetime.fromisoformat(clean_date_str)
                # Convert to UTC if it has a timezone
                if parsed_date.tzinfo:
                    parsed_date = parsed_date.astimezone(datetime.UTC)
                else:
                    parsed_date = parsed_date.replace(tzinfo=datetime.UTC)
            except ValueError:
                continue
                
            if parsed_date >= window_start:
                commits_in_window += 1
                month_key = parsed_date.strftime("%Y-%m")
                monthly_series_map[month_key] += 1
                
            if parsed_date >= window_90d:
                active_authors_90d.add(author)

        # Calculate Bus Factor (minimum set of authors covering >= 80% of total commits)
        bus_factor = 0
        commits_accum = 0
        target = total_commits * 0.8
        for _, count in authors.most_common():
            bus_factor += 1
            commits_accum += count
            if commits_accum >= target:
                break

        # Calculate days since last commit
        days_since_last_commit = 0
        if last_commit_date:
            try:
                clean_last = last_commit_date.replace("Z", "+00:00")
                parsed_last = datetime.datetime.fromisoformat(clean_last)
                if parsed_last.tzinfo:
                    parsed_last = parsed_last.astimezone(datetime.UTC)
                else:
                    parsed_last = parsed_last.replace(tzinfo=datetime.UTC)
                days_since_last_commit = max((now - parsed_last).days, 0)
            except ValueError:
                pass

        # Sort the monthly series chronologically
        monthly_commit_series = [{"month": k, "count": monthly_series_map[k]} for k in sorted(monthly_series_map.keys())]

        top_contributors = []
        for name, count in authors.most_common(50):
            pct = round((count / total_commits) * 100, 1) if total_commits > 0 else 0
            top_contributors.append({"name": name, "commits": count, "pct": pct})

        return {
            "total_commits": total_commits,
            "total_contributors": len(authors),
            "active_contributors_90d": len(active_authors_90d),
            "bus_factor": bus_factor,
            "first_commit_date": first_commit_date,
            "last_commit_date": last_commit_date,
            "days_since_last_commit": days_since_last_commit,
            "commits_in_window": commits_in_window,
            "analysis_window_days": since_days,
            "monthly_commit_series": monthly_commit_series,
            "top_contributors": top_contributors
        }
