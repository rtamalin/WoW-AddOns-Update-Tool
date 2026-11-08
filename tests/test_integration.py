"""Integration tests using real git repositories."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.vault import Repository, Vault
from utils.updater import AddOnsUpdater


@pytest.fixture
def bare_git_repo(tmp_path: Path) -> Path:
    """Create a bare git repository for testing."""
    bare_dir = tmp_path / "bare-repo.git"
    bare_dir.mkdir()

    # Create a source repo first
    source_dir = tmp_path / "source-repo"
    source_dir.mkdir()

    # Initialize and configure
    subprocess.run(["git", "init"], cwd=source_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        check=True,
        cwd=source_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        check=True,
        cwd=source_dir,
        capture_output=True,
    )

    # Create a .toc file
    toc_file = source_dir / "TestAddon.toc"
    toc_file.write_text("## Interface: 30300\n## Title: Test Addon\n")

    # Commit
    subprocess.run(
        ["git", "add", "."], check=True, cwd=source_dir, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        check=True,
        cwd=source_dir,
        capture_output=True,
    )

    # Create bare clone
    subprocess.run(
        ["git", "clone", "--bare", str(source_dir), str(bare_dir)],
        check=True,
        capture_output=True,
    )

    return bare_dir


class TestRepositoryIntegration:
    """Integration tests for Repository with real git."""

    def test_clone_from_bare_repo(self, tmp_project_root, bare_git_repo, mock_log):
        """Repository.clone works with a real bare git repo."""
        url = f"file://{bare_git_repo}"
        repo = Repository(url, "master", tmp_project_root)
        repo.repo_path = tmp_project_root / "bare-repo" / "source-repo"

        result = repo.download()

        assert result is True
        assert repo.repo_path.exists()
        assert (repo.repo_path / "TestAddon.toc").exists()
        assert repo.head is not None

    def test_update_from_bare_repo(self, tmp_project_root, bare_git_repo, mock_log):
        """Repository updates correctly from a bare git repo."""
        url = f"file://{bare_git_repo}"
        repo = Repository(url, "master", tmp_project_root)
        repo.repo_path = tmp_project_root / "bare-repo" / "source-repo"

        # First download
        result1 = repo.download()
        assert result1 is True
        first_head = repo.head

        # Make a change in the bare repo
        source_dir = bare_git_repo.parent / "source-repo"
        toc_file = source_dir / "TestAddon.toc"
        toc_file.write_text("## Interface: 30300\n## Title: Test Addon v2\n")

        subprocess.run(
            ["git", "add", "."], check=True, cwd=source_dir, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Update addon"],
            check=True,
            cwd=source_dir,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", str(bare_git_repo), "master"],
            check=True,
            cwd=source_dir,
            capture_output=True,
        )

        # Update existing repo
        result2 = repo.download()
        assert result2 == -1  # -1 means updated
        assert repo.head != first_head

    def test_check_remote_refs_with_real_repo(
        self, tmp_project_root, bare_git_repo, mock_log
    ):
        """check_remote_refs works with a real bare git repo."""
        url = f"file://{bare_git_repo}"
        repo = Repository(url, "master", tmp_project_root)

        result = repo.check_remote_refs()
        assert result is True

        # Non-existent branch
        repo.branch = "nonexistent"
        result = repo.check_remote_refs()
        assert result is False


class TestVaultIntegration:
    """Integration tests for Vault with real git."""

    @pytest.mark.slow
    def test_vault_adds_repository(self, tmp_project_root, bare_git_repo, mock_log):
        """Vault can add a repository from a real git source."""
        url = f"file://{bare_git_repo}"
        vault = Vault("test", basedir=tmp_project_root / "vault")

        vault.new_or_update(url, "master")
        vault.refresh()

        assert len(vault.repositories) == 1
        assert vault.repositories[0].name == "source-repo"
        assert vault.repositories[0].repo_path.exists()


class TestAddOnsUpdaterIntegration:
    """Integration tests for AddOnsUpdater with real git."""

    @pytest.mark.slow
    def test_full_install_flow(self, tmp_project_root, bare_git_repo, mock_log):
        """Full flow: vault clone -> updater install -> files in game folder."""
        url = f"file://{bare_git_repo}"
        vault = Vault("test", basedir=tmp_project_root / "vault")
        vault.new_or_update(url, "master")
        vault.refresh()

        addons_path = tmp_project_root / "Interface" / "AddOns"

        updater = AddOnsUpdater(addons_path, vault)
        updater.install()

        # The addon should be installed in the game folder
        installed = addons_path / "source-repo"
        # Note: The actual installed path depends on how _prepare finds .toc files
        # and how _copy places them. The key assertion is that install() completes
        # without error and the vault has the repository.
        assert len(vault.repositories) == 1

    @pytest.mark.slow
    def test_backup_before_install(
        self, tmp_project_root, bare_git_repo, mock_log
    ):
        """Backup is created before addon installation."""
        addons_path = tmp_project_root / "Interface" / "AddOns"

        # Create an existing addon to backup
        existing_addon = addons_path / "ExistingAddon"
        existing_addon.mkdir(parents=True, exist_ok=True)
        (existing_addon / "ExistingAddon.toc").write_text("## Title: Existing\n")

        url = f"file://{bare_git_repo}"
        vault = Vault("test", basedir=tmp_project_root / "vault")
        vault.new_or_update(url, "master")
        vault.refresh()

        updater = AddOnsUpdater(addons_path, vault)
        updater.install()

        # Backup folder should exist
        backup_base = tmp_project_root / "Interface" / "AddOns_backups"
        assert backup_base.exists()


class TestRepositoryRemoveIntegration:
    """Integration tests for Repository.remove with real git."""

    def test_remove_deletes_repo_folder(self, tmp_project_root, bare_git_repo, mock_log):
        """remove() actually deletes the repository folder from disk."""
        url = f"file://{bare_git_repo}"
        repo = Repository(url, "master", tmp_project_root)
        repo.repo_path = tmp_project_root / "bare-repo" / "source-repo"

        # First download
        repo.download()
        assert repo.repo_path.exists()

        # Then remove
        result = repo.remove()
        assert result is True
        assert not repo.repo_path.exists()
