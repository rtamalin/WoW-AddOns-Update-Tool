"""Tests for the vault module (Repository and Vault classes)."""

import pickle
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.vault import Repository, Vault


@pytest.fixture
def sample_vault_basedir(tmp_path: Path) -> Path:
    """Create a sample vault basedir with cache db."""
    basedir = tmp_path / "vault" / "testuser"
    basedir.mkdir(parents=True)
    cache_db = basedir / "cache.db"
    # Create an empty cache
    with open(cache_db, "wb") as f:
        pickle.dump([], f)
    return basedir


class TestRepositoryInit:
    """Tests for Repository.__init__."""

    def test_parses_author_and_name(self, sample_vault_basedir):
        """Repository extracts author and name from URL."""
        # The regex patterns in vault.py:
        # author: re_search("(?:github|gitlab).com/(.*)/", url).group(1)
        # name:   re_search("(?s:.*)/(.*)", url).group(1)
        mock_match = MagicMock()
        mock_match.group.side_effect = [
            "testuser",    # group(1) for author regex
            "test-addon",  # group(1) for name regex
        ]

        with patch("utils.vault.re_search", return_value=mock_match):
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )

        assert repo.author == "testuser"
        assert repo.name == "test-addon"
        assert repo.branch == "main"

    def test_invalid_url_exits(self, sample_vault_basedir, mock_vault_log):
        """Repository exits on invalid URL."""
        with patch("utils.vault.sys.exit") as mock_exit:
            with patch("utils.vault.re_search", return_value=None):
                try:
                    Repository(
                        "not-a-valid-url",
                        "main",
                        sample_vault_basedir,
                    )
                except AttributeError:
                    # sys.exit is patched, so code continues and tries to
                    # access self.author which doesn't exist
                    pass
                mock_exit.assert_called_once_with(1)


class TestRepositoryReset:
    """Tests for Repository._reset."""

    @patch("utils.vault.reset")
    @patch("utils.vault.clean")
    def test_reset_success(self, mock_clean, mock_reset, sample_vault_basedir):
        """_reset returns True on success."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")
        repo.repo_path.mkdir(exist_ok=True, parents=True)

        result = repo._reset()

        assert result is True
        mock_reset.assert_called_once()
        mock_clean.assert_called_once()

    @patch("utils.vault.reset", side_effect=Exception("fail"))
    def test_reset_failure(self, mock_reset, sample_vault_basedir, mock_vault_log):
        """_reset returns False and logs error on failure."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")

        result = repo._reset()

        assert result is False
        mock_vault_log.error.assert_called_once()


class TestRepositoryUpdate:
    """Tests for Repository._update."""

    @patch("utils.vault.Repo")
    @patch("utils.vault.fetch")
    @patch("utils.vault.pull")
    @patch("utils.vault.clean")
    @patch("utils.vault.reset")
    def test_update_success(
        self, mock_reset, mock_clean, mock_pull, mock_fetch, mock_repo_class, sample_vault_basedir
    ):
        """_update returns True on success."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")
        repo.repo_path.mkdir(exist_ok=True, parents=True)

        mock_head = MagicMock()
        mock_head.hex.return_value = "abc123"
        mock_repo_instance = MagicMock()
        mock_repo_instance.__getitem__ = MagicMock(return_value=b"abc123")
        mock_repo_instance.head = MagicMock(return_value=mock_head)
        mock_repo_class.return_value = mock_repo_instance
        mock_fetch.return_value = MagicMock(
            refs={b"refs/heads/main": b"abc123"}
        )

        result = repo._update()

        assert result is True
        mock_fetch.assert_called_once()
        mock_pull.assert_called_once()

    @patch("utils.vault.Repo")
    @patch("utils.vault.fetch")
    @patch("utils.vault.pull")
    @patch("utils.vault.clean")
    @patch("utils.vault.reset")
    def test_update_failure_on_fetch(
        self, mock_reset, mock_clean, mock_pull, mock_fetch, mock_repo_class,
        sample_vault_basedir, mock_vault_log
    ):
        """_update returns False when fetch/pull fails."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")
        repo.repo_path.mkdir(exist_ok=True, parents=True)

        mock_head = MagicMock()
        mock_head.hex.return_value = "abc123"
        mock_repo_instance = MagicMock()
        mock_repo_instance.__getitem__ = MagicMock(return_value=b"abc123")
        mock_repo_instance.head = MagicMock(return_value=mock_head)
        mock_repo_class.return_value = mock_repo_instance
        mock_fetch.return_value = MagicMock(
            refs={b"refs/heads/main": b"abc123"}
        )
        mock_pull.side_effect = Exception("pull failed")

        result = repo._update()

        assert result is False
        mock_vault_log.error.assert_called_once()

    @patch("utils.vault.Repo")
    def test_update_skip_when_reset_fails(
        self, mock_repo_class, sample_vault_basedir, mock_vault_log
    ):
        """_update returns True (skips update) when _reset fails."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        # Mock _reset to return False
        # Note: _update still calls Repo(self.repo_path).head().hex() at the end
        # even when _reset fails, so we need to mock Repo properly
        mock_head = MagicMock()
        mock_head.hex.return_value = "abc123"
        mock_repo_instance = MagicMock()
        mock_repo_instance.head = MagicMock(return_value=mock_head)
        mock_repo_class.return_value = mock_repo_instance

        with patch.object(repo, "_reset", return_value=False):
            result = repo._update()

        # When _reset fails, _update skips the fetch/pull block but still
        # returns True (it just doesn't update)
        assert result is True


class TestRepositoryCheckRemoteRefs:
    """Tests for Repository.check_remote_refs."""

    @patch("utils.vault.ls_remote")
    def test_branch_exists(self, mock_ls_remote, sample_vault_basedir):
        """check_remote_refs returns True when branch exists."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )

        mock_result = MagicMock()
        mock_result.refs = {b"refs/heads/main": b"abc123"}
        mock_ls_remote.return_value = mock_result

        result = repo.check_remote_refs()

        assert result is True

    @patch("utils.vault.ls_remote")
    def test_branch_missing(self, mock_ls_remote, sample_vault_basedir, mock_vault_log):
        """check_remote_refs returns False when branch doesn't exist."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.branch = "develop"
        mock_result = MagicMock()
        mock_result.refs = {b"refs/heads/main": b"abc123"}
        mock_ls_remote.return_value = mock_result

        result = repo.check_remote_refs()

        assert result is False
        mock_vault_log.error.assert_called_once()

    @patch("utils.vault.ls_remote", side_effect=Exception("network error"))
    def test_ls_remote_exception(
        self, mock_ls_remote, sample_vault_basedir, mock_vault_log
    ):
        """check_remote_refs returns False on ls_remote exception."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )

        result = repo.check_remote_refs()

        assert result is False
        mock_vault_log.error.assert_called_once()


class TestRepositoryDownload:
    """Tests for Repository.download."""

    @patch("utils.vault.Repo")
    @patch("utils.vault.clone")
    def test_new_clone(self, mock_clone, mock_repo_class, sample_vault_basedir):
        """download returns True for a new clone."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")
        repo.repo_path.mkdir(exist_ok=True, parents=True)

        mock_head = MagicMock()
        mock_head.hex.return_value = "abc123"
        mock_repo_instance = MagicMock()
        mock_repo_instance.head = MagicMock(return_value=mock_head)
        mock_repo_class.return_value = mock_repo_instance

        result = repo.download()

        assert result is True
        mock_clone.assert_called_once()

    @patch("utils.vault.Repo")
    @patch("utils.vault.clone", side_effect=FileExistsError())
    @patch.object(Repository, "_update", return_value=True)
    def test_existing_update(
        self, mock_update, mock_clone, mock_repo_class, sample_vault_basedir
    ):
        """download returns -1 for an existing repo that was updated."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")

        mock_head = MagicMock()
        mock_head.hex.return_value = "abc123"
        mock_repo_instance = MagicMock()
        mock_repo_instance.head = MagicMock(return_value=mock_head)
        mock_repo_class.return_value = mock_repo_instance

        result = repo.download()

        assert result == -1

    @patch("utils.vault.Repo")
    @patch("utils.vault.clone", side_effect=FileExistsError())
    @patch.object(Repository, "_update", return_value=False)
    def test_existing_update_fails(
        self, mock_update, mock_clone, mock_repo_class, sample_vault_basedir, mock_vault_log
    ):
        """download returns False when existing repo update fails."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")

        result = repo.download()

        assert result is False
        mock_vault_log.error.assert_called_once()

    @patch("utils.vault.clone", side_effect=Exception("other error"))
    def test_clone_other_exception(
        self, mock_clone, sample_vault_basedir, mock_vault_log
    ):
        """download returns False on non-FileExistsError exceptions."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")

        result = repo.download()

        assert result is False
        mock_vault_log.error.assert_called_once()


class TestRepositoryRemove:
    """Tests for Repository.remove."""

    @patch("utils.vault.rmtree")
    def test_remove_success(self, mock_rmtree, sample_vault_basedir):
        """remove returns True on success."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")

        result = repo.remove()

        assert result is True

    @patch("utils.vault.rmtree", side_effect=Exception("fail"))
    def test_remove_failure(self, mock_rmtree, sample_vault_basedir, mock_vault_log):
        """remove returns False and logs warning on failure."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")

        result = repo.remove()

        assert result is False
        mock_vault_log.warning.assert_called_once()


class TestRepositoryCheckout:
    """Tests for Repository.checkout."""

    @patch.object(Repository, "download", return_value=True)
    @patch("utils.vault.rmtree")
    def test_checkout_success(
        self, mock_rmtree, mock_download, sample_vault_basedir
    ):
        """checkout returns True on success."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")

        result = repo.checkout("develop")

        assert result is True
        mock_rmtree.assert_called_once()
        mock_download.assert_called_once()

    @patch.object(Repository, "download", side_effect=Exception("fail"))
    @patch("utils.vault.rmtree")
    def test_checkout_failure(
        self, mock_rmtree, mock_download, sample_vault_basedir, mock_vault_log
    ):
        """checkout returns False on failure."""
        with patch("utils.vault.re_search") as mock:
            mock.return_value = MagicMock(
                group=MagicMock(side_effect=lambda i: ["testuser", "test-addon"][i])
            )
            repo = Repository(
                "https://github.com/testuser/test-addon",
                "main",
                sample_vault_basedir,
            )
        repo.repo_path = Path("/tmp/test-repo")

        result = repo.checkout("develop")

        assert result is False
        mock_vault_log.error.assert_called_once()


class TestVaultInit:
    """Tests for Vault.__init__."""

    def test_creates_basedir_if_missing(self, tmp_path, mock_vault_log):
        """Vault creates basedir if it doesn't exist."""
        # Patch the basedir path to use tmp_path
        with patch("utils.vault.Path") as mock_path:
            mock_basedir = MagicMock()
            mock_basedir.is_dir.return_value = False
            mock_basedir.exists.return_value = False
            mock_basedir.mkdir = MagicMock()
            mock_basedir.__truediv__ = MagicMock(return_value=mock_basedir)
            mock_path.return_value = mock_basedir

            # Mock _load to avoid pickle issues
            with patch.object(Vault, "_load"):
                vault = Vault("newuser")
                vault.basedir = mock_basedir

            mock_basedir.mkdir.assert_called_once()

    def test_loads_existing_cache(self, tmp_path, mock_vault_log):
        """Vault loads existing cache from DB."""
        basedir = tmp_path / "vault" / "testuser"
        basedir.mkdir(parents=True)
        cache_db = basedir / "cache.db"

        # Create the cache file
        with open(cache_db, "wb") as f:
            pickle.dump([], f)

        # Mock load to return a mock repo
        mock_repo = MagicMock()
        mock_repo.repo_path = Path("/some/path")

        with patch("utils.vault.load", return_value=[mock_repo]):
            vault = Vault("testuser")
            vault.basedir = basedir
            vault.cache_db_path = cache_db
            vault._load()

        assert len(vault.repositories) == 1


class TestVaultLoad:
    """Tests for Vault._load."""

    def test_loads_empty_cache(self, sample_vault_basedir, mock_vault_log):
        """_load handles empty cache gracefully."""
        vault = Vault("testuser")
        vault.basedir = sample_vault_basedir
        vault.cache_db_path = sample_vault_basedir / "cache.db"

        vault._load()

        assert vault.repositories == []

    def test_clears_and_populates_repositories(
        self, sample_vault_basedir, mock_vault_log
    ):
        """_load clears existing repos and loads from cache."""
        vault = Vault("testuser")
        vault.basedir = sample_vault_basedir
        vault.cache_db_path = sample_vault_basedir / "cache.db"

        # Pre-populate with old data
        old_repo = MagicMock()
        old_repo.repo_path = Path("/old/path")
        vault.repositories = [old_repo]

        # Create new cache with a different repo
        new_repo = MagicMock()
        new_repo.repo_path = Path("/new/path")

        with patch("utils.vault.load", return_value=[new_repo]):
            vault._load()

        assert len(vault.repositories) == 1
        assert vault.repositories[0].repo_path == Path("/new/path")

    def test_skips_duplicate_repos(self, sample_vault_basedir, mock_vault_log):
        """_load skips repos with duplicate repo_path."""
        vault = Vault("testuser")
        vault.basedir = sample_vault_basedir
        vault.cache_db_path = sample_vault_basedir / "cache.db"

        duplicate_repo = MagicMock()
        duplicate_repo.repo_path = Path("/same/path")

        with patch("utils.vault.load", return_value=[duplicate_repo, duplicate_repo]):
            vault._load()

        assert len(vault.repositories) == 1


class TestVaultNewOrUpdate:
    """Tests for Vault.new_or_update."""

    @patch.object(Repository, "download", return_value=True)
    @patch.object(Repository, "check_remote_refs", return_value=True)
    def test_new_repository(
        self, mock_check, mock_download, sample_vault_basedir, mock_vault_log
    ):
        """new_or_update adds a new repository."""
        vault = Vault("testuser")
        vault.basedir = sample_vault_basedir
        vault.cache_db_path = sample_vault_basedir / "cache.db"

        vault.new_or_update(
            "https://github.com/testuser/new-addon", "main"
        )
        vault.threads = []  # Mock threads list
        vault.refresh()

        assert len(vault.repositories) == 1
        assert vault.repositories[0].name == "new-addon"

    @patch.object(Repository, "download", return_value=True)
    @patch.object(Repository, "check_remote_refs", return_value=True)
    @patch.object(Repository, "checkout")
    def test_branch_change_triggers_checkout(
        self, mock_checkout, mock_check, mock_download,
        sample_vault_basedir, mock_vault_log
    ):
        """new_or_update triggers checkout when branch changes."""
        vault = Vault("testuser")
        vault.basedir = sample_vault_basedir
        vault.cache_db_path = sample_vault_basedir / "cache.db"

        # Add existing repo with old branch
        existing_repo = MagicMock()
        existing_repo.repo_path = sample_vault_basedir / "testuser" / "test-addon"
        existing_repo.branch = "develop"
        vault.repositories = [existing_repo]

        vault.new_or_update(
            "https://github.com/testuser/test-addon", "main"
        )
        vault.threads = []
        vault.refresh()

        mock_checkout.assert_called_once_with("develop")


class TestVaultRefresh:
    """Tests for Vault.refresh."""

    @patch("utils.vault.dump")
    def test_refresh_saves_cache(self, mock_dump, sample_vault_basedir, mock_vault_log):
        """refresh saves the session to cache DB."""
        vault = Vault("testuser")
        vault.basedir = sample_vault_basedir
        vault.cache_db_path = sample_vault_basedir / "cache.db"

        mock_repo = MagicMock()
        mock_repo.repo_path = Path("/some/path")
        vault.session = [mock_repo]
        vault.threads = []

        # Mock _load to avoid pickle issues
        with patch.object(vault, "_load"):
            vault.refresh()

        mock_dump.assert_called_once()
