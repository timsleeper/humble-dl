import hashlib
import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from humble_dl.cli import app

runner = CliRunner()


class TestAuthValidation:
    def test_no_auth_option_exits_with_error(self, tmp_path):
        result = runner.invoke(app, ["download", "-l", str(tmp_path)])
        assert result.exit_code == 2
        assert "One of" in result.output

    def test_multiple_auth_options_exits_with_error(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("dummy")
        result = runner.invoke(
            app, ["download", "-l", str(tmp_path), "-c", str(cookie_file), "-s", "session_val"]
        )
        assert result.exit_code == 2
        assert "Only one" in result.output

    def test_auto_and_browser_mutually_exclusive(self, tmp_path):
        result = runner.invoke(
            app, ["download", "-l", str(tmp_path), "--auto", "--browser", "chrome"]
        )
        assert result.exit_code == 2
        assert "Only one" in result.output

    def test_auto_and_session_auth_mutually_exclusive(self, tmp_path):
        result = runner.invoke(app, ["download", "-l", str(tmp_path), "--auto", "-s", "value"])
        assert result.exit_code == 2
        assert "Only one" in result.output


class TestFilterValidation:
    def test_include_and_exclude_mutually_exclusive(self, tmp_path):
        result = runner.invoke(
            app,
            ["download", "-l", str(tmp_path), "-s", "cookie", "-i", "pdf", "-e", "mobi"],
        )
        assert result.exit_code == 2
        assert "cannot both be set" in result.output


class TestHelpOutput:
    def test_help_shows_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "download" in result.output
        assert "verify" in result.output

    def test_download_help_shows_all_options(self):
        result = runner.invoke(app, ["download", "--help"])
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

    def test_verify_help_shows_options(self):
        result = runner.invoke(app, ["verify", "--help"])
        assert result.exit_code == 0
        assert "--library-path" in result.output


class TestLibraryPathRequired:
    def test_missing_library_path_exits(self):
        result = runner.invoke(app, ["download", "-s", "cookie_value"])
        assert result.exit_code != 0


class TestConcurrentValidation:
    def test_concurrent_below_min(self, tmp_path):
        result = runner.invoke(app, ["download", "-l", str(tmp_path), "-s", "cookie", "-n", "0"])
        assert result.exit_code != 0

    def test_concurrent_above_max(self, tmp_path):
        result = runner.invoke(app, ["download", "-l", str(tmp_path), "-s", "cookie", "-n", "21"])
        assert result.exit_code != 0


class TestSuccessfulInvocation:
    def test_session_auth_invokes_run(self, tmp_path):
        with patch("humble_dl.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(
                app, ["download", "-l", str(tmp_path), "-s", "my_session_cookie"]
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
        with patch("humble_dl.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(app, ["download", "-l", str(tmp_path), "--auto"])
            assert result.exit_code == 0
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["auto_cookies"] is True
            assert call_kwargs["cookie_file"] is None
            assert call_kwargs["session_auth"] is None
            assert call_kwargs["browser"] is None

    def test_browser_invokes_run(self, tmp_path):
        with patch("humble_dl.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(app, ["download", "-l", str(tmp_path), "-b", "firefox"])
            assert result.exit_code == 0
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["browser"] == "firefox"

    def test_all_options_passed_through(self, tmp_path):
        with patch("humble_dl.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(
                app,
                [
                    "download",
                    "-l",
                    str(tmp_path),
                    "-s",
                    "cookie",
                    "--trove",
                    "--update",
                    "-p",
                    "ebook",
                    "-p",
                    "audio",
                    "-i",
                    "pdf",
                    "-i",
                    "epub",
                    "-k",
                    "key1",
                    "-k",
                    "key2",
                    "-n",
                    "10",
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
        with patch("humble_dl.cli._run", new_callable=AsyncMock) as mock_run:
            result = runner.invoke(app, ["download", "-l", str(tmp_path), "-c", str(cookie_file)])
            assert result.exit_code == 0
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["cookie_file"] == cookie_file


class TestVerifyCommand:
    def test_no_cache_file_exits(self, tmp_path):
        result = runner.invoke(app, ["verify", "-l", str(tmp_path)])
        assert result.exit_code == 1
        assert "No .cache.json" in result.output

    def test_empty_verification_data_exits(self, tmp_path):
        cache = {"order1:old.pdf": {"url_last_modified": "some-date"}}
        (tmp_path / ".cache.json").write_text(json.dumps(cache))
        result = runner.invoke(app, ["verify", "-l", str(tmp_path)])
        assert result.exit_code == 1
        assert "No verification data" in result.output

    def test_all_files_ok(self, tmp_path):
        content = b"hello world"
        file_path = tmp_path / "book.pdf"
        file_path.write_bytes(content)

        cache = {
            "order1:book.pdf": {
                "local_path": str(file_path),
                "file_size": len(content),
                "file_md5": hashlib.md5(content).hexdigest(),
            }
        }
        (tmp_path / ".cache.json").write_text(json.dumps(cache))

        result = runner.invoke(app, ["verify", "-l", str(tmp_path)])
        assert result.exit_code == 0
        assert "1 OK" in result.output
        assert "0 failed" in result.output

    def test_missing_file_detected(self, tmp_path):
        cache = {
            "order1:gone.pdf": {
                "local_path": str(tmp_path / "gone.pdf"),
                "file_size": 100,
                "file_md5": "abc123",
            }
        }
        (tmp_path / ".cache.json").write_text(json.dumps(cache))

        result = runner.invoke(app, ["verify", "-l", str(tmp_path)])
        assert result.exit_code == 1
        assert "1 failed" in result.output
        assert "Missing" in result.output

    def test_size_mismatch_detected(self, tmp_path):
        file_path = tmp_path / "short.pdf"
        file_path.write_bytes(b"short")

        cache = {
            "order1:short.pdf": {
                "local_path": str(file_path),
                "file_size": 9999,
                "file_md5": "irrelevant",
            }
        }
        (tmp_path / ".cache.json").write_text(json.dumps(cache))

        result = runner.invoke(app, ["verify", "-l", str(tmp_path)])
        assert result.exit_code == 1
        assert "Size Mismatch" in result.output

    def test_md5_mismatch_detected(self, tmp_path):
        content = b"original"
        file_path = tmp_path / "modified.pdf"
        file_path.write_bytes(b"tampered")

        cache = {
            "order1:modified.pdf": {
                "local_path": str(file_path),
                "file_size": len(b"tampered"),
                "file_md5": hashlib.md5(content).hexdigest(),
            }
        }
        (tmp_path / ".cache.json").write_text(json.dumps(cache))

        result = runner.invoke(app, ["verify", "-l", str(tmp_path)])
        assert result.exit_code == 1
        assert "MD5 Mismatch" in result.output

    def test_skips_entries_without_verification_data(self, tmp_path):
        content = b"good"
        file_path = tmp_path / "good.pdf"
        file_path.write_bytes(content)

        cache = {
            "order1:old.pdf": {"url_last_modified": "some-date"},
            "order1:good.pdf": {
                "local_path": str(file_path),
                "file_size": len(content),
                "file_md5": hashlib.md5(content).hexdigest(),
            },
        }
        (tmp_path / ".cache.json").write_text(json.dumps(cache))

        result = runner.invoke(app, ["verify", "-l", str(tmp_path)])
        assert result.exit_code == 0
        assert "1 OK" in result.output
        assert "1 skipped" in result.output
