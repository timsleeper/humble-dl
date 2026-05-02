from pathlib import Path

import pytest

from humblebundle_downloader.models import (
    AsmJsGame,
    CacheEntry,
    DownloadItem,
    DownloadStatus,
    DownloadType,
    Order,
    Product,
    TroveProduct,
)


class TestDownloadType:
    def test_values(self):
        assert DownloadType.URL.value == "url"
        assert DownloadType.ASM_JS.value == "asm_js"
        assert DownloadType.EXTERNAL.value == "external"


class TestDownloadStatus:
    def test_values(self):
        assert DownloadStatus.PENDING.value == "pending"
        assert DownloadStatus.DOWNLOADING.value == "downloading"
        assert DownloadStatus.COMPLETED.value == "completed"
        assert DownloadStatus.SKIPPED.value == "skipped"
        assert DownloadStatus.FAILED.value == "failed"


class TestDownloadItem:
    def test_creation_with_required_fields(self):
        item = DownloadItem(
            cache_key="order123:file.pdf",
            url="https://example.com/file.pdf",
            local_path=Path("/tmp/file.pdf"),
            download_type=DownloadType.URL,
        )
        assert item.cache_key == "order123:file.pdf"
        assert item.url == "https://example.com/file.pdf"
        assert item.local_path == Path("/tmp/file.pdf")
        assert item.download_type == DownloadType.URL
        assert item.platform == ""
        assert item.extension == ""
        assert item.uploaded_at is None
        assert item.md5 is None

    def test_creation_with_all_fields(self):
        item = DownloadItem(
            cache_key="trove:game.zip",
            url="https://example.com/game.zip",
            local_path=Path("/tmp/game.zip"),
            download_type=DownloadType.URL,
            platform="windows",
            extension="zip",
            uploaded_at="1715769045",
            md5="abc123",
        )
        assert item.platform == "windows"
        assert item.uploaded_at == "1715769045"
        assert item.md5 == "abc123"

    def test_frozen_immutability(self):
        item = DownloadItem(
            cache_key="key",
            url="url",
            local_path=Path("/tmp/f"),
            download_type=DownloadType.URL,
        )
        with pytest.raises(AttributeError):
            item.cache_key = "new_key"


class TestAsmJsGame:
    def test_creation(self):
        html_item = DownloadItem(
            cache_key="order:game.html",
            url="https://example.com/game",
            local_path=Path("/tmp/game/game.html"),
            download_type=DownloadType.URL,
        )
        game = AsmJsGame(
            html_item=html_item,
            game_name="mygame",
            asm_name="mygame_asm",
            order_id="order123",
            local_folder=Path("/tmp/game"),
        )
        assert game.html_item is html_item
        assert game.game_name == "mygame"
        assert game.asm_name == "mygame_asm"
        assert game.order_id == "order123"
        assert game.local_folder == Path("/tmp/game")

    def test_frozen_immutability(self):
        html_item = DownloadItem(
            cache_key="k",
            url="u",
            local_path=Path("/tmp/f"),
            download_type=DownloadType.URL,
        )
        game = AsmJsGame(
            html_item=html_item,
            game_name="g",
            asm_name="a",
            order_id="o",
            local_folder=Path("/tmp"),
        )
        with pytest.raises(AttributeError):
            game.game_name = "other"


class TestProduct:
    def test_creation_with_defaults(self):
        item = DownloadItem(
            cache_key="k",
            url="u",
            local_path=Path("/tmp/f"),
            download_type=DownloadType.URL,
        )
        product = Product(human_name="Test Game", downloads=(item,))
        assert product.human_name == "Test Game"
        assert len(product.downloads) == 1
        assert product.external_links == ()

    def test_with_external_links(self):
        product = Product(
            human_name="Test",
            downloads=(),
            external_links=("https://steam.com/game",),
        )
        assert len(product.external_links) == 1

    def test_mixed_download_types(self):
        url_item = DownloadItem(
            cache_key="k1",
            url="u1",
            local_path=Path("/tmp/f1"),
            download_type=DownloadType.URL,
        )
        html_item = DownloadItem(
            cache_key="k2",
            url="u2",
            local_path=Path("/tmp/f2"),
            download_type=DownloadType.URL,
        )
        asm_game = AsmJsGame(
            html_item=html_item,
            game_name="g",
            asm_name="a",
            order_id="o",
            local_folder=Path("/tmp"),
        )
        product = Product(
            human_name="Mixed",
            downloads=(url_item, asm_game),
        )
        assert len(product.downloads) == 2
        assert isinstance(product.downloads[0], DownloadItem)
        assert isinstance(product.downloads[1], AsmJsGame)


class TestOrder:
    def test_creation(self):
        product = Product(human_name="Game", downloads=())
        order = Order(
            order_id="abc123",
            bundle_title="Humble Indie Bundle",
            products=(product,),
        )
        assert order.order_id == "abc123"
        assert order.bundle_title == "Humble Indie Bundle"
        assert len(order.products) == 1


class TestTroveProduct:
    def test_creation(self):
        item = DownloadItem(
            cache_key="trove:game.zip",
            url="signed_url",
            local_path=Path("/tmp/game.zip"),
            download_type=DownloadType.URL,
            platform="windows",
        )
        trove = TroveProduct(
            human_name="Trove Game",
            downloads=(item,),
        )
        assert trove.human_name == "Trove Game"
        assert len(trove.downloads) == 1


class TestCacheEntry:
    def test_defaults(self):
        entry = CacheEntry()
        assert entry.url_last_modified is None
        assert entry.uploaded_at is None
        assert entry.md5 is None

    def test_with_values(self):
        entry = CacheEntry(
            url_last_modified="Wed, 15 May 2024 10:30:45 GMT",
            uploaded_at="1715769045",
            md5="abc123def456",
        )
        assert entry.url_last_modified == "Wed, 15 May 2024 10:30:45 GMT"

    def test_mutable(self):
        # CacheEntry is NOT frozen, unlike the other models
        entry = CacheEntry()
        entry.url_last_modified = "new value"
        assert entry.url_last_modified == "new value"
