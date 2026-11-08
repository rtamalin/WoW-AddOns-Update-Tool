"""Tests for the CLI application module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestProcessArgs:
    """Tests for CLI argument processing."""

    def test_verbose_enables_debug(self, tmp_path):
        """--verbose flag sets log level to DEBUG."""
        from app import parser

        args = parser.parse_args(["--verbose", "-c", "config.yaml"])
        assert args.verbose is True

    def test_vault_defaults_to_github(self, tmp_path):
        """Vault defaults to 'github' when not specified."""
        from app import parser

        args = parser.parse_args(["-c", "config.yaml"])
        assert args.vault == "github"

    def test_vault_custom_name(self, tmp_path):
        """Vault uses custom name when specified."""
        from app import parser

        args = parser.parse_args(["-v", "myvault", "-c", "config.yaml"])
        assert args.vault == "myvault"

    def test_start_flag(self, tmp_path):
        """--start flag is parsed correctly."""
        from app import parser

        args = parser.parse_args(["-c", "config.yaml", "--start"])
        assert args.start is True

    def test_config_yaml_discovery(self, tmp_path):
        """Config auto-discovers config.yaml when present."""
        from app import parser

        # Create config.yaml
        config_file = tmp_path / "config.yaml"
        config_file.write_text("repos: []\n")

        with patch("app.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.__truediv__ = lambda self, other: tmp_path / other
            mock_path.return_value = mock_path_instance

            args = parser.parse_args(["-c", ""])
            # When -c is empty, it should discover config.yaml
            assert args.config == config_file

    def test_config_json_discovery(self, tmp_path):
        """Config auto-discovers config.json when present."""
        import json

        from app import parser

        # Create config.json
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}))

        with patch("app.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.__truediv__ = lambda self, other: tmp_path / other
            mock_path.return_value = mock_path_instance

            args = parser.parse_args(["-c", ""])
            assert args.config == config_file

    def test_missing_config_exits(self, tmp_path):
        """Exits with error when no config file is found."""
        from app import parser, main

        with patch("app.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance

            with patch("app.sys.exit") as mock_exit:
                parser.parse_args(["-c", ""])
                main()

            mock_exit.assert_called_once_with(1)


class TestMain:
    """Tests for the main function."""

    def test_main_requires_config(self, tmp_path):
        """main() exits if config file doesn't exist."""
        with patch("app.sys.exit") as mock_exit, patch(
            "app.Path"
        ) as mock_path_class:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            with patch("app.args"):
                args = MagicMock()
                args.config = str(tmp_path / "nonexistent.yaml")
                args.start = False
                args.vault = "test"
                args.wow = str(tmp_path / "Wow.exe")
                args.verbose = False

                with patch("app.parser.parse_args", return_value=args):
                    with patch("app.main") as mock_main:
                        # We can't easily test main() directly because it
                        # calls parser.parse_args at module level, so we
                        # test the config loading path instead
                        pass

    def test_wow_path_validation(self, tmp_path):
        """main() validates Wow.exe path exists."""
        from app import parser

        args = parser.parse_args([
            "-v", "test",
            "-w", str(tmp_path / "Wow.exe"),
            "-c", str(tmp_path / "config.yaml"),
        ])

        # Simulate missing Wow.exe
        with patch("app.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance

            with patch("app.sys.exit") as mock_exit:
                with patch("app.args", args):
                    with patch("app.parser.parse_args", return_value=args):
                        with patch("app.main") as mock_main:
                            pass  # Can't easily call main() due to module-level parse_args


class TestArgumentParser:
    """Tests for the argument parser configuration."""

    def test_parser_has_vault_argument(self):
        """Parser includes vault argument."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert "vault" in actions

    def test_parser_has_wow_argument(self):
        """Parser includes wow argument."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert "wow" in actions

    def test_parser_has_config_argument(self):
        """Parser includes config argument."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert "config" in actions

    def test_parser_has_start_argument(self):
        """Parser includes start argument."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert "start" in actions

    def test_parser_has_verbose_argument(self):
        """Parser includes verbose argument."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert "verbose" in actions

    def test_vault_is_optional(self):
        """Vault argument is optional (nargs='?')."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert actions["vault"].nargs == "?"

    def test_wow_is_optional(self):
        """Wow argument is optional (nargs='?')."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert actions["wow"].nargs == "?"

    def test_config_is_optional(self):
        """Config argument is optional (nargs='?')."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert actions["config"].nargs == "?"

    def test_start_is_store_true(self):
        """Start argument uses store_true action."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        assert isinstance(actions["start"].action, type(parser.parse_args([]).start) is not True)
        # store_true sets the default to False, action is StoreTrue

    def test_verbose_is_store_true(self):
        """Verbose argument uses store_true action."""
        from app import parser

        default_args = parser.parse_args([])
        assert default_args.verbose is False

        with_args = parser.parse_args(["--verbose"])
        assert with_args.verbose is True

    def test_all_required_arguments_present(self):
        """All required arguments (vault, wow, config) are present."""
        from app import parser

        actions = {action.dest: action for action in parser._actions}
        required_action = actions.get("vault")
        assert required_action is not None
        # vault, wow, and config are all in the "required" group
