from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from humblebundle_downloader.cli import app

runner = CliRunner()


class TestAuthValidation:
    def test_no_auth_option_exits_with_error(self, tmp_path):
        result = runner.invoke(app, ["-l", str(tmp_path)])
        assert result.exit_code == 2
        assert "One of" in result.output

    def test_multiple_auth_options_exits_with_error(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("dummy")
        result = runner.invoke(
            app, ["-l", str(tmp_path), "-c", str(cookie_file), "-s", "session_val"]
        )
        assert result.exit_code == 2
        assert "Only one" in result.output

    def test_auto_and_browser_mutually_exclusive(self, tmp_path):
        result = runner.invoke(
            app, ["-l", str(tmp_path), "--auto", "--browser", "chrome"]
        )
        assert result.exit_code == 2
        assert "Only one" in result.output

    def test_auto_and_session_auth_mutually_exclusive(self, tmp_path):
        result = runner.invoke(
            app, ["-l", str(tmp_path), "--auto", "-s", "value"]
        )
        assert result.exit_code == 2
        assert "Only one" in result.output


class TestFilterValidation:
    def test_include_and_exclude_mutually_exclusive(self, tmp_path):
        result = runner.invoke(
            app,
            ["-l", str(tmp_path), "-s", "cookie", "-i", "pdf", "-e", "mobi"],
        )
        assert result.exit_code == 2
        assert "cannot both be set" in result.output


class TestHelpOutput:
    def test_help_shows_all_options(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--library-path" in result.output
        assert "--cookie-file" in result.output
        assert "--session-auth" in result.output
        assert "--browser" in result.output
        assert "--auto" in result.output
        assert "--trove" in result.output
        assert "--update" in result.output
        assert "--platform" in result.output
        assert "--include" in result.output
        assert "--exclude" in result.output
        assert "--keys" in result.output
        assert "--concurrent" in result.output
        assert "--verbose" in result.output


class TestLibraryPathRequired:
    def test_missing_library_path_exits(self):
        result = runner.invoke(app, ["-s", "cookie_value"])
        assert result.exit_code != 0


class TestConcurrentValidation:
    def test_concurrent_below_min(self, tmp_path):
        result = runner.invoke(
            app, ["-l", str(tmp_path), "-s", "cookie", "-n", "0"]
        )
        assert result.exit_code != 0

    def test_concurrent_above_max(self, tmp_path):
        result = runner.invoke(
            app, ["-l", str(tmp_path), "-s", "cookie", "-n", "21"]
        )
        assert result.exit_code != 0


class TestSuccessfulInvocation:
    def test_session_auth_invokes_run(self, tmp_path):
        with patch("humblebundle_downloader.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(
                app, ["-l", str(tmp_path), "-s", "my_session_cookie"]
            )
            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["session_auth"] == "my_session_cookie"
            assert call_kwargs["library_path"] == tmp_path
            assert call_kwargs["concurrent"] == 5
            assert call_kwargs["trove"] is False
            assert call_kwargs["update"] is False

    def test_auto_cookies_invokes_run(self, tmp_path):
        with patch("humblebundle_downloader.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(app, ["-l", str(tmp_path), "--auto"])
            assert result.exit_code == 0
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["auto_cookies"] is True
            assert call_kwargs["cookie_file"] is None
            assert call_kwargs["session_auth"] is None
            assert call_kwargs["browser"] is None

    def test_browser_invokes_run(self, tmp_path):
        with patch("humblebundle_downloader.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(
                app, ["-l", str(tmp_path), "-b", "firefox"]
            )
            assert result.exit_code == 0
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["browser"] == "firefox"

    def test_all_options_passed_through(self, tmp_path):
        with patch("humblebundle_downloader.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(
                app,
                [
                    "-l", str(tmp_path),
                    "-s", "cookie",
                    "--trove",
                    "--update",
                    "-p", "ebook",
                    "-p", "audio",
                    "-i", "pdf",
                    "-i", "epub",
                    "-k", "key1",
                    "-k", "key2",
                    "-n", "10",
                    "--verbose",
                ],
            )
            assert result.exit_code == 0
            kw = mock_run.call_args.kwargs
            assert kw["trove"] is True
            assert kw["update"] is True
            assert kw["platform_include"] == ["ebook", "audio"]
            assert kw["ext_include"] == ["pdf", "epub"]
            assert kw["purchase_keys"] == ["key1", "key2"]
            assert kw["concurrent"] == 10

    def test_cookie_file_invokes_run(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("dummy cookie")
        with patch("humblebundle_downloader.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(
                app, ["-l", str(tmp_path), "-c", str(cookie_file)]
            )
            assert result.exit_code == 0
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["cookie_file"] == cookie_file
