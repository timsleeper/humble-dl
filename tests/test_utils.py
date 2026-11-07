import os
from pathlib import Path

import pytest

from humble_dl.utils import clean_name, fs_path, rename_old_file


class TestCleanName:
    def test_basic_alphanumeric(self):
        assert clean_name("Hello World 123") == "Hello World 123"

    def test_plus_replaced_with_underscore(self):
        assert clean_name("Game+DLC") == "Game_DLC"

    def test_colon_replaced_with_dash(self):
        assert clean_name("Title: Subtitle") == "Title - Subtitle"

    def test_allowed_special_chars_preserved(self):
        assert clean_name("file_name-v2.0 [special]") == "file_name-v2.0 [special]"

    def test_disallowed_chars_stripped(self):
        assert clean_name("file@name#with$bad&chars") == "filenamewithbadchars"

    def test_trailing_dots_stripped(self):
        assert clean_name("name...") == "name"

    def test_leading_trailing_whitespace_stripped(self):
        assert clean_name("  padded  ") == "padded"

    def test_empty_string(self):
        assert clean_name("") == ""

    def test_only_dots(self):
        assert clean_name("...") == ""

    def test_only_special_chars(self):
        assert clean_name("@#$%") == ""

    def test_combined_replacements(self):
        assert clean_name("Game+DLC: Ep2...") == "Game_DLC - Ep2"

    def test_unicode_letters_preserved(self):
        assert clean_name("Résumé café") == "Résumé café"

    def test_unicode_disallowed_stripped(self):
        assert clean_name("price€100") == "price100"

    def test_multiple_colons(self):
        # ":" is replaced with " -", so "A:B:C" becomes "A -B -C"
        assert clean_name("A:B:C") == "A -B -C"

    def test_multiple_plusses(self):
        assert clean_name("A+B+C") == "A_B_C"

    def test_real_world_example_broken_sword(self):
        # From the original code comment
        assert clean_name("Broken Sword 5 - the Serpent's Curse") == (
            "Broken Sword 5 - the Serpents Curse"
        )


class TestRenameOldFile:
    def test_renames_existing_file(self, tmp_path):
        f = tmp_path / "game.zip"
        f.write_text("content")
        result = rename_old_file(f, "2024-01-15")
        assert result == tmp_path / "game_2024-01-15.zip"
        assert result.exists()
        assert not f.exists()
        assert result.read_text() == "content"

    def test_returns_none_for_missing_file(self, tmp_path):
        f = tmp_path / "missing.zip"
        result = rename_old_file(f, "2024-01-15")
        assert result is None

    def test_returns_none_for_directory(self, tmp_path):
        d = tmp_path / "subdir"
        d.mkdir()
        result = rename_old_file(d, "2024-01-15")
        assert result is None

    def test_preserves_extension(self, tmp_path):
        f = tmp_path / "book.pdf"
        f.write_text("pdf content")
        result = rename_old_file(f, "old")
        assert result.suffix == ".pdf"
        assert result.stem == "book_old"

    def test_file_without_extension(self, tmp_path):
        f = tmp_path / "README"
        f.write_text("readme")
        result = rename_old_file(f, "backup")
        assert result == tmp_path / "README_backup"
        assert result.exists()

    def test_multiple_dots_in_filename(self, tmp_path):
        f = tmp_path / "archive.tar.gz"
        f.write_text("data")
        result = rename_old_file(f, "2024-01-15")
        # Path.stem is "archive.tar", Path.suffix is ".gz"
        assert result == tmp_path / "archive.tar_2024-01-15.gz"


class TestFsPath:
    BSL = chr(92)  # one backslash, no escaping games
    EXT = BSL * 2 + "?" + BSL  # the extended-length prefix value
    EXT_UNC = BSL * 2 + "?" + BSL + "UNC" + BSL  # the UNC extended-length prefix

    @pytest.mark.skipif(os.name == "nt", reason="POSIX behaviour")
    def test_identity_on_posix(self):
        p = Path("/tmp/a/b/c.txt")
        assert fs_path(p) is p

    @pytest.mark.skipif(os.name != "nt", reason="Windows behaviour")
    def test_prefixes_local_drive_on_windows(self):
        out = str(fs_path(Path("C:/Users/x/deep/file.txt")))
        assert out.startswith(self.EXT + "C:")
        assert out.endswith("file.txt")

    @pytest.mark.skipif(os.name != "nt", reason="Windows behaviour")
    def test_prefixes_unc_on_windows(self):
        out = str(fs_path(Path("//server/share/dir/file.txt")))
        assert out.startswith(self.EXT_UNC + "server")

    @pytest.mark.skipif(os.name != "nt", reason="Windows behaviour")
    def test_idempotent_on_windows(self):
        once = fs_path(Path("C:/a/b.txt"))
        assert fs_path(once) == once

    @pytest.mark.skipif(os.name != "nt", reason="Windows long-path write")
    def test_long_path_write_roundtrip(self, tmp_path):
        deep = tmp_path
        for _ in range(6):
            deep = deep / ("x" * 50)
        target = deep / ("y" * 50 + ".txt")
        assert len(str(target)) > 260  # a plain open() would fail here
        fp = fs_path(target)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("ok")
        assert fp.read_text() == "ok"
