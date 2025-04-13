"""
GitHub repository handling module.
"""
import os
import git
import glob
from pathlib import Path
from typing import List, Dict, Any

class GitHubRepo:
    def __init__(self, repo_url: str, base_dir: str, github_token: str = None):
        self.repo_url = repo_url
        self.base_dir = Path(base_dir)
        self.github_token = github_token
        self.repo_name = self._extract_repo_name()
        self.repo_path = self.base_dir / self.repo_name
       
    def _extract_repo_name(self) -> str:
        """Extract repository name from the URL."""
        # Handle both HTTPS and SSH URLs
        repo_url = self.repo_url  # Initialize repo_url with self.repo_url
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
       
        # Get the last part of the URL (repo name)
        return os.path.basename(repo_url)
   
    def clone(self) -> Path:
        """Clone the repository."""
        if self.repo_path.exists():
            # Repository already exists, just pull latest changes
            repo = git.Repo(self.repo_path)
            origin = repo.remotes.origin
            origin.pull()
        else:
            # Clone new repository
            git.Repo.clone_from(self.repo_url, self.repo_path)
       
        return self.repo_path
   
    def get_code_files(self) -> List[Dict[str, Any]]:
        """Get all code files from the repository."""
        code_extensions = [
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h',
            '.hpp', '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs'
        ]
       
        code_files = []
       
        for ext in code_extensions:
            pattern = str(self.repo_path) + f"/**/*{ext}"
            files = glob.glob(pattern, recursive=True)
           
            for file_path in files:
                rel_path = os.path.relpath(file_path, str(self.repo_path))
               
                # Skip files in .git directory, node_modules, etc.
                if any(part.startswith('.') for part in Path(rel_path).parts) or \
                   'node_modules' in Path(rel_path).parts or \
                   'venv' in Path(rel_path).parts:
                    continue
               
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                   
                    code_files.append({
                        'path': rel_path,
                        'full_path': file_path,
                        'content': content,
                        'extension': ext
                    })
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
       
        return code_files