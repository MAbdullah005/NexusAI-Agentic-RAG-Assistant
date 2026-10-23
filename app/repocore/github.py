import asyncio
import httpx
import subprocess
import tempfile
import shutil
import os
from fastapi import HTTPException
from .file_filter import filter_files

# --- GitHub API + clone helpers ---

def parse_github_url(github_url: str) -> dict:
    """extract owner and repo name from url"""
    parts = github_url.rstrip("/").split("/")
    return {"owner": parts[-2], "repo": parts[-1].replace(".git", "")}


async def get_repo_metadata(owner: str, repo: str) -> dict:
    """get default branch and size of repo"""
    MAX_REPO_SIZE_KB=500_000 #50MB
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}"
            )
            response.raise_for_status()
            data = response.json()
            if data["size"]>MAX_REPO_SIZE_KB:
                raise HTTPException(
                    status_code=413,
                    detail="Repository is too large to process "
                )
            return {
                "default_branch": data["default_branch"],
                "size_kb": data["size"],
            }
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail="Failed to fetch repo metadata"
            )


async def download_repo(owner: str, repo: str, branch: str) -> dict:
    """shallow-clone the repo at its latest commit and return local file paths

    returns dict: {"root": <dir>, "files": [list of file paths], "temp_dir": ...}
    """
    temp_dir = tempfile.mkdtemp()
    url = f"https://github.com/{owner}/{repo}.git"

    proc = await asyncio.to_thread(
        subprocess.run,
        ["git", "clone", "--depth", "1", "--single-branch", "--branch", branch, url, temp_dir],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to clone repository: {proc.stderr.strip()}",
        )

    root = temp_dir

    file_paths = []

    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            file_paths.append(os.path.join(dirpath, filename))
    filtered=filter_files(file_paths,root)

    return {
        "filtered files":filtered,
        "root": root,
        "files": file_paths,
        "temp_dir": temp_dir
    }

