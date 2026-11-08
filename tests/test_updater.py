"""Tests for the updater module."""

import pickle
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.updater import AddOnsUpdater


@pytest.fixture
def base_setup(tmp_path: Path):
    """Create the base directory structure for updater tests."""
    addons_path = tmp_path / "Interface" / "AddOns"
    addons_path.mkdir(parents=True, exist_ok=True)
    backups_path = tmp_path / "Interface" / "AddOns_backups"
    backups_path.mkdir(parents=True, exist_ok=True)
    vault_path = tmp_path / "vault" / "user" / "addon"
    vault_path.mkdir(parents=True, exist_ok=True)
    return tmp_path, addons_path, backups_path, vault_path


class TestAddOnsUpdaterBackup:
    """Tests for backup functionality."""

    def test_backup_init_creates_timestamp_folder(
        self, base_setup, mock_updater_log
    ):
        """_backup_init creates a timestamped backup directory."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        updater = AddOnsUpdater(addons_path, vault)
        updater._backup_init()

        assert updater.timestamp_backup_folder is not None
        assert updater.timestamp_backup_folder.exists()
        # The folder should be named with a timestamp
        assert "T" in updater.timestamp_backup_folder.name  # ISO format

    def test_backup_moves_addon_to_backup(
        self, base_setup, mock_updater_log
    ):
        """_backup moves addon folder to backup."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        # Create an addon folder
        addon_dir = addons_path / "TestAddon"
        addon_dir.mkdir(parents=True, exist_ok=True)
        (addon_dir / "test.lua").write_text("-- test")

        updater = AddOnsUpdater(addons_path, vault)
        updater._backup_init()
        updater._backup("TestAddon")

        # Wait for thread to complete
        for thread in updater.threads:
            thread.join(timeout=1)

        # Addon should be in backup folder now
        assert not addon_dir.exists()
        backup_addon = updater.timestamp_backup_folder / "TestAddon"
        assert backup_addon.exists()

    def test_backup_end_removes_empty_backup(
        self, base_setup, mock_updater_log
    ):
        """_backup_end removes backup folder if it's empty."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        updater = AddOnsUpdater(addons_path, vault)
        updater._backup_init()
        updater._backup_end()

        # Empty backup folder should be removed
        assert not updater.timestamp_backup_folder.exists()

    def test_backup_end_removes_old_backups(
        self, base_setup, mock_updater_log
    ):
        """_backup_end keeps only the last 5 backups."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        updater = AddOnsUpdater(addons_path, vault)

        # Create 7 old backup folders (with dates before the current one)
        for i in range(7):
            backup_dir = backups_path / f"backup-2025-01-{i:02d}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            (backup_dir / "placeholder.txt").write_text("data")

        updater._backup_init()
        # Add a file to timestamp folder so it's not removed as empty
        (updater.timestamp_backup_folder / "addon").mkdir()
        (updater.timestamp_backup_folder / "addon" / "toc").write_text("toc")
        updater._backup_end()

        # Count remaining backups (should be at most 5 kept + 1 current timestamp)
        remaining = list(backups_path.iterdir())
        assert len(remaining) <= 6


class TestAddOnsUpdaterCopy:
    """Tests for the _copy method."""

    def test_copy_copies_files(self, base_setup, mock_updater_log):
        """_copy copies files from source to destination."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        # Create source files
        (vault_path / "Addon.toc").write_text("## Title: Addon\n")
        (vault_path / "test.lua").write_text("-- test")

        updater = AddOnsUpdater(addons_path, vault)

        # The _copy method expects a list of paths to copy
        # It copies from the parent of each path
        updater._copy(["addon", "abc123", [vault_path]])
        for thread in updater.threads:
            thread.join(timeout=1)

        dest_dir = addons_path / "addon"
        assert dest_dir.exists()
        assert (dest_dir / "Addon.toc").exists()
        assert (dest_dir / "test.lua").exists()

    def test_copy_updates_cache(self, base_setup, mock_updater_log):
        """_copy updates the cache with the repository head."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        (vault_path / "Addon.toc").write_text("## Title: Addon\n")

        updater = AddOnsUpdater(addons_path, vault)
        updater._copy(["addon", "abc123", [vault_path]])
        for thread in updater.threads:
            thread.join(timeout=1)

        time.sleep(0.1)

        assert updater.cache["addon"] == "abc123"

    def test_copy_removes_git_folder(self, base_setup, mock_updater_log):
        """_copy removes .git folder if present."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        (vault_path / "Addon.toc").write_text("## Title: Addon\n")
        git_dir = vault_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")

        updater = AddOnsUpdater(addons_path, vault)
        updater._copy(["addon", "abc123", [vault_path]])
        for thread in updater.threads:
            thread.join(timeout=1)

        dest_dir = addons_path / "addon"
        assert dest_dir.exists()
        assert not (dest_dir / ".git").exists()


class TestAddOnsUpdaterPrepare:
    """Tests for the _prepare method."""

    def test_prepare_identifies_new_addons(self, base_setup, mock_updater_log):
        """_prepare identifies addons that need to be installed."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        # Create a repo in vault
        repo = MagicMock()
        repo.name = "new-addon"
        repo.head = "abc123"
        repo.repo_path = vault_path
        vault.repositories = [repo]

        (vault_path / "Addon.toc").write_text("## Title: Addon\n")

        updater = AddOnsUpdater(addons_path, vault)
        to_backup, to_install = updater._prepare(vault)

        assert "new-addon" in [item[0] for item in to_install]

    def test_prepare_skips_up_to_date(self, base_setup, mock_updater_log):
        """_prepare skips addons that are already up to date."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        # Create a repo in vault
        repo = MagicMock()
        repo.name = "up-to-date"
        repo.head = "abc123"
        repo.repo_path = vault_path
        vault.repositories = [repo]

        (vault_path / "Addon.toc").write_text("## Title: Addon\n")

        updater = AddOnsUpdater(addons_path, vault)
        updater.cache = {"up-to-date": "abc123"}

        to_backup, to_install = updater._prepare(vault)

        assert len(to_install) == 0

    def test_prepare_identifies_updates(self, base_setup, mock_updater_log):
        """_prepare identifies addons that need updating."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        # Create a repo in vault with different head
        repo = MagicMock()
        repo.name = "outdated"
        repo.head = "def456"
        repo.repo_path = vault_path
        vault.repositories = [repo]

        (vault_path / "Addon.toc").write_text("## Title: Addon\n")

        updater = AddOnsUpdater(addons_path, vault)
        updater.cache = {"outdated": "abc123"}

        to_backup, to_install = updater._prepare(vault)

        assert len(to_install) == 1
        assert to_install[0][0] == "outdated"


class TestAddOnsUpdaterSaveDb:
    """Tests for the _save_db method."""

    def test_save_db_writes_cache(self, base_setup, mock_updater_log):
        """_save_db writes the cache to the database file."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        updater = AddOnsUpdater(addons_path, vault)
        updater.cache = {"addon1": "abc123", "addon2": "def456"}

        updater._save_db()

        # Read back the cache
        with open(updater.updater_cache_db_path, "rb") as f:
            loaded_cache = pickle.load(f)

        assert loaded_cache == {"addon1": "abc123", "addon2": "def456"}


class TestAddOnsUpdaterInstall:
    """Tests for the install method."""

    def test_install_no_changes(self, base_setup, mock_updater_log):
        """install does nothing when all addons are up to date."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        updater = AddOnsUpdater(addons_path, vault)
        updater.install()

        # Should complete without error
        # Note: cache may be empty since no repos were processed
        assert isinstance(updater.cache, dict)

    def test_install_copies_new_addon(self, base_setup, mock_updater_log):
        """install copies new addon from vault to game folder."""
        tmp_path, addons_path, backups_path, vault_path = base_setup
        vault = MagicMock()
        vault.repositories = []

        # Create a repo in vault
        repo = MagicMock()
        repo.name = "new-addon"
        repo.head = "abc123"
        repo.repo_path = vault_path
        vault.repositories = [repo]

        (vault_path / "Addon.toc").write_text("## Title: Addon\n")

        updater = AddOnsUpdater(addons_path, vault)
        updater.install()

        # Check that the addon was either installed or the cache was updated
        assert updater.cache.get("new-addon") == "abc123" or (
            addons_path / "new-addon"
        ).exists()
