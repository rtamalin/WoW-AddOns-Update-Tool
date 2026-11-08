"""Shared fixtures for all tests."""

import logging
import pickle
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_project_root(tmp_path: Path) -> Path:
    """A temporary directory that mimics the project root structure."""
    (tmp_path / "vault").mkdir()
    (tmp_path / "Interface" / "AddOns").mkdir(parents=True)
    (tmp_path / "Interface" / "AddOns_backups").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mock_log():
    """Mock the project logger to avoid color output during tests."""
    with patch("utils.log.log") as mock:
        mock.setLevel = MagicMock()
        yield mock


@pytest.fixture
def mock_vault_log():
    """Mock the logger in utils.vault module namespace."""
    with patch("utils.vault.log") as mock:
        yield mock


@pytest.fixture
def mock_updater_log():
    """Mock the logger in utils.updater module namespace."""
    with patch("utils.updater.log") as mock:
        yield mock


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create a real git repo in a temp dir with a .toc file for testing."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()

    import subprocess

    subprocess.run(["git", "init", str(repo_dir)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        check=True,
        cwd=repo_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        check=True,
        cwd=repo_dir,
        capture_output=True,
    )

    toc_file = repo_dir / "TestAddon.toc"
    toc_file.write_text("## Interface: 30300\n## Title: Test Addon\n")

    subprocess.run(["git", "add", "."], check=True, cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        check=True,
        cwd=repo_dir,
        capture_output=True,
    )

    return repo_dir


@pytest.fixture
def temp_git_repo_with_branch(tmp_path: Path, branch: str = "main"):
    """Create a real git repo with a specific branch."""
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()

    import subprocess

    subprocess.run(["git", "init", str(repo_dir)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        check=True,
        cwd=repo_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        check=True,
        cwd=repo_dir,
        capture_output=True,
    )

    toc_file = repo_dir / "TestAddon.toc"
    toc_file.write_text("## Interface: 30300\n## Title: Test Addon\n")
    subprocess.run(["git", "add", "."], check=True, cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        check=True,
        cwd=repo_dir,
        capture_output=True,
    )

    if branch and branch != "master" and branch != "main":
        subprocess.run(
            ["git", "branch", branch],
            check=True,
            cwd=repo_dir,
            capture_output=True,
        )

    bare_dir = tmp_path / "bare-repo.git"
    subprocess.run(
        ["git", "clone", "--bare", str(repo_dir), str(bare_dir)],
        check=True,
        capture_output=True,
    )

    return repo_dir, bare_dir


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    """Create a sample config.yaml file."""
    config = tmp_path / "config.yaml"
    config.write_text(
        "github:\n"
        "  basedir: ./vault\n"
        "  cache_db: cache.db\n"
        "repos:\n"
        '  - url: "https://github.com/testuser/test-addon"\n'
        '    branch: "main"\n'
    )
    return config


@pytest.fixture
def sample_json_config(tmp_path: Path) -> Path:
    """Create a sample config.json file."""
    import json

    config = tmp_path / "config.json"
    data = {
        "github": {
            "basedir": "./vault",
            "cache_db": "cache.db",
        },
        "repos": [
            {"url": "https://github.com/testuser/test-addon", "branch": "main"},
        ],
    }
    config.write_text(json.dumps(data))
    return config
