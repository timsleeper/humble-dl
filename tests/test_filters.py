import pytest

from humblebundle_downloader.filters import (
    get_file_ext,
    should_download_ext,
    should_download_file,
    should_download_platform,
)


class TestShouldDownloadExt:
    # --- include logic ---

    def test_include_with_values_match(self):
        assert should_download_ext("pdf", include=["pdf", "epub"]) is True

    def test_include_with_values_no_match(self):
        assert should_download_ext("mobi", include=["pdf", "epub"]) is False

    def test_include_case_insensitive(self):
        assert should_download_ext("PDF", include=["pdf"]) is True
        assert should_download_ext("pdf", include=["PDF"]) is True
        assert should_download_ext("ePub", include=["EPub"]) is True

    def test_include_empty_allows_all(self):
        assert should_download_ext("pdf", include=[]) is True
        assert should_download_ext("anything", include=[]) is True

    def test_include_none_allows_all(self):
        assert should_download_ext("pdf", include=None) is True

    # --- exclude logic ---

    def test_exclude_with_values_blocks_match(self):
        assert should_download_ext("pdf", exclude=["pdf", "epub"]) is False

    def test_exclude_with_values_allows_non_match(self):
        assert should_download_ext("mobi", exclude=["pdf", "epub"]) is True

    def test_exclude_case_insensitive(self):
        assert should_download_ext("PDF", exclude=["pdf"]) is False
        assert should_download_ext("pdf", exclude=["PDF"]) is False

    def test_exclude_empty_allows_all(self):
        assert should_download_ext("pdf", exclude=[]) is True

    def test_exclude_none_allows_all(self):
        assert should_download_ext("pdf", exclude=None) is True

    # --- include takes priority over exclude ---

    def test_include_overrides_exclude(self):
        # When both are provided, include wins
        assert should_download_ext("pdf", include=["pdf"], exclude=["pdf"]) is True
        assert should_download_ext("mobi", include=["pdf"], exclude=[]) is False

    # --- no filters ---

    def test_no_filters_allows_all(self):
        assert should_download_ext("pdf") is True
        assert should_download_ext("exe") is True
        assert should_download_ext("") is True

    # --- partial match should not pass ---

    def test_partial_match_does_not_pass(self):
        assert should_download_ext("df", include=["pdf"]) is False
        assert should_download_ext("pd", include=["pdf"]) is False


class TestShouldDownloadPlatform:
    def test_none_allows_all(self):
        assert should_download_platform("ebook", platform_include=None) is True
        assert should_download_platform("audio", platform_include=None) is True

    def test_empty_list_allows_all(self):
        assert should_download_platform("ebook", platform_include=[]) is True

    def test_all_keyword_allows_all(self):
        assert should_download_platform("ebook", platform_include=["all"]) is True
        assert should_download_platform("windows", platform_include=["all"]) is True

    def test_all_keyword_case_insensitive(self):
        assert should_download_platform("ebook", platform_include=["ALL"]) is True
        assert should_download_platform("ebook", platform_include=["All"]) is True

    def test_filter_specific_platform(self):
        assert should_download_platform("audio", platform_include=["audio"]) is True
        assert should_download_platform("ebook", platform_include=["audio"]) is False

    def test_filter_case_insensitive(self):
        assert should_download_platform("AUDIO", platform_include=["audio"]) is True
        assert should_download_platform("audio", platform_include=["AUDIO"]) is True

    def test_multiple_platforms(self):
        platforms = ["ebook", "audio"]
        assert should_download_platform("ebook", platform_include=platforms) is True
        assert should_download_platform("audio", platform_include=platforms) is True
        assert should_download_platform("video", platform_include=platforms) is False

    def test_all_mixed_with_others(self):
        # "all" in the list means everything passes
        assert should_download_platform("video", platform_include=["all", "ebook"]) is True


class TestGetFileExt:
    def test_simple_extension(self):
        assert get_file_ext("file.pdf") == "pdf"

    def test_uppercase_extension(self):
        assert get_file_ext("FILE.PDF") == "pdf"

    def test_multiple_dots(self):
        assert get_file_ext("archive.tar.gz") == "gz"

    def test_no_extension(self):
        assert get_file_ext("README") == ""

    def test_dot_at_end(self):
        assert get_file_ext("file.") == ""

    def test_hidden_file(self):
        assert get_file_ext(".gitignore") == "gitignore"

    def test_empty_string(self):
        assert get_file_ext("") == ""


class TestShouldDownloadFile:
    def test_matches_extension_from_filename(self):
        assert should_download_file("book.pdf", ext_include=["pdf"]) is True
        assert should_download_file("book.mobi", ext_include=["pdf"]) is False

    def test_excludes_extension_from_filename(self):
        assert should_download_file("book.pdf", ext_exclude=["pdf"]) is False
        assert should_download_file("book.mobi", ext_exclude=["pdf"]) is True

    def test_no_filters(self):
        assert should_download_file("anything.xyz") is True

    def test_complex_filename(self):
        assert should_download_file(
            "Game_v2.1_linux.tar.gz", ext_include=["gz"]
        ) is True
        assert should_download_file(
            "Game_v2.1_linux.tar.gz", ext_include=["tar"]
        ) is False

    def test_filename_with_query_params(self):
        # The caller should strip query params before calling, but test the raw behavior
        assert get_file_ext("file.pdf?token=abc") == "pdf?token=abc"

    def test_case_insensitive_matching(self):
        assert should_download_file("Book.PDF", ext_include=["pdf"]) is True
        assert should_download_file("Book.Pdf", ext_exclude=["pdf"]) is False
