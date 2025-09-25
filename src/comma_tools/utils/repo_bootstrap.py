"""Helpers for cloning and caching external repositories used by comma-tools."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "comma-tools" / "repos"


@dataclass(slots=True)
class RepoSpec:
    """Configuration describing how to obtain an external repository."""

    name: str
    url: str
    branch: str
    env_path_var: Optional[str] = None
    env_branch_var: Optional[str] = None

    def cache_path(self, base: Path) -> Path:
        return base / self.name


REPOS = (
    RepoSpec(
        name="openpilot",
        url="https://github.com/anteew/openpilot.git",
        branch="devin2",
        env_path_var="OPENPILOT_PATH",
        env_branch_var="OPENPILOT_BRANCH",
    ),
    RepoSpec(
        name="opendbc",
        url="https://github.com/anteew/opendbc.git",
        branch="devin2",
        env_path_var="OPENDBC_PATH",
        env_branch_var="OPENDBC_BRANCH",
    ),
)


def _run_git(args: list[str], cwd: Optional[Path] = None) -> None:
    command = ["git", *args]
    subprocess.check_call(command, cwd=cwd)


def _checkout_branch(repo_path: Path, branch: str) -> None:
    # Fetch the remote branch if it is not available locally.
    try:
        _run_git(["rev-parse", "--verify", branch], cwd=repo_path)
    except subprocess.CalledProcessError:
        _run_git(["fetch", "origin", branch], cwd=repo_path)
    _run_git(["checkout", branch], cwd=repo_path)


def ensure_repo(spec: RepoSpec, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
    """Ensure that the repository described by *spec* exists locally.

    The lookup order is:
    1. Environment override (e.g., OPENPILOT_PATH) if present
    2. Cached clone under ~/.cache/comma-tools/repos
    3. Fresh clone from the configured remote
    """

    # Environment override takes priority and should not be modified.
    if spec.env_path_var:
        env_path = os.getenv(spec.env_path_var)
        if env_path:
            repo_path = Path(env_path).expanduser().resolve()
            if not (repo_path / ".git").exists():
                raise FileNotFoundError(
                    f"{spec.env_path_var} points to {repo_path}, but it is not a git repository"
                )
            return repo_path

    cache_root.mkdir(parents=True, exist_ok=True)
    repo_path = spec.cache_path(cache_root)

    branch = os.getenv(spec.env_branch_var, spec.branch) if spec.env_branch_var else spec.branch

    if repo_path.exists():
        if not (repo_path / ".git").exists():
            raise FileExistsError(
                f"Expected {repo_path} to be a git repository for {spec.name}, but .git is missing"
            )
        # Refresh to target branch if possible, but avoid touching dirty working trees.
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
        if status.stdout.strip():
            # Leave dirty tree untouched; assume user knows what they're doing.
            return repo_path

        _run_git(["fetch", "origin"], cwd=repo_path)
        _checkout_branch(repo_path, branch)
        _run_git(["reset", "--hard", f"origin/{branch}"], cwd=repo_path)
        return repo_path

    _run_git(["clone", "--branch", branch, "--single-branch", spec.url, str(repo_path)])
    return repo_path


def ensure_all_repos(cache_root: Path = DEFAULT_CACHE_ROOT) -> dict[str, Path]:
    """Ensure all known external repositories are available locally."""

    paths: dict[str, Path] = {}
    for spec in REPOS:
        paths[spec.name] = ensure_repo(spec, cache_root)
    return paths
