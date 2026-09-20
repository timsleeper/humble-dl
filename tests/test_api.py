import httpx
import pytest
import respx

from humble_dl.api import HumbleBundleAPI
from humble_dl.exceptions import APIError
from humble_dl.models import AsmJsGame, DownloadItem, DownloadType


LIBRARY_HTML = """
<html>
<script id="user-home-json-data" type="application/json">
{"gamekeys": ["key1", "key2", "key3"]}
</script>
</html>
"""

LIBRARY_HTML_NO_DATA = "<html><body>No data</body></html>"

ORDER_JSON = {
    "product": {"human_name": "Humble Indie Bundle 1"},
    "subproducts": [
        {
            "human_name": "Super Game",
            "downloads": [
                {
                    "platform": "windows",
                    "download_struct": [
                        {
                            "url": {"web": "https://dl.humblebundle.com/supergame.zip?token=abc"},
                            "md5": "d41d8cd98f00b204e9800998ecf8427e",
                        },
                        {
                            "external_link": "https://store.steampowered.com/app/12345",
                        },
                    ],
                },
                {
                    "platform": "linux",
                    "download_struct": [
                        {
                            "url": {
                                "web": "https://dl.humblebundle.com/supergame_linux.tar.gz?t=x"
                            },
                        },
                    ],
                },
            ],
        },
    ],
}

ORDER_JSON_WITH_ASM = {
    "product": {"human_name": "Asm Bundle"},
    "subproducts": [
        {
            "human_name": "Browser Game",
            "downloads": [
                {
                    "platform": "windows",
                    "download_struct": [
                        {
                            "asm_config": {"display_item": "mygame"},
                            "asm_manifest": {"asmFile": "asmjs/play/mygame_asm/file.js"},
                        },
                    ],
                },
            ],
        },
    ],
}

TROVE_CATALOG_PAGE_1 = [
    {
        "human-name": "Trove Game 1",
        "date_added": "1600000000",
        "downloads": {
            "windows": {
                "url": {"web": "revolutionsoftware/trove_game.zip"},
                "machine_name": "trovegame_windows",
                "uploaded_at": "1715769045",
                "md5": "abc123",
            },
        },
    },
]

TROVE_CATALOG_EMPTY = []

ASMJS_HTML = """
<html>
<script id="webpack-asm-player-data" type="application/json">
{"asmOptions": {"manifest": {"game.js": "https://cdn.example.com/game.js", "game.data": "https://cdn.example.com/game.data"}}}
</script>
</html>
"""


@pytest.fixture
def api():
    client = httpx.AsyncClient(base_url="https://www.humblebundle.com")
    return HumbleBundleAPI(client)


class TestGetPurchaseKeys:
    @respx.mock
    async def test_returns_gamekeys(self, api):
        respx.get("https://www.humblebundle.com/home/library").mock(
            return_value=httpx.Response(200, text=LIBRARY_HTML)
        )
        keys = await api.get_purchase_keys()
        assert keys == ["key1", "key2", "key3"]

    @respx.mock
    async def test_raises_on_missing_data(self, api):
        respx.get("https://www.humblebundle.com/home/library").mock(
            return_value=httpx.Response(200, text=LIBRARY_HTML_NO_DATA)
        )
        with pytest.raises(APIError, match="Unable to parse"):
            await api.get_purchase_keys()

    @respx.mock
    async def test_raises_on_http_error(self, api):
        respx.get("https://www.humblebundle.com/home/library").mock(
            return_value=httpx.Response(403)
        )
        with pytest.raises(APIError, match="Failed to fetch library"):
            await api.get_purchase_keys()


class TestGetOrder:
    @respx.mock
    async def test_parses_order_with_products(self, api, tmp_path):
        respx.get("https://www.humblebundle.com/api/v1/order/order123?all_tpkds=true").mock(
            return_value=httpx.Response(200, json=ORDER_JSON)
        )

        order = await api.get_order("order123", tmp_path)
        assert order.order_id == "order123"
        assert order.bundle_title == "Humble Indie Bundle 1"
        assert len(order.products) == 1

        product = order.products[0]
        assert product.human_name == "Super Game"
        # 2 URL downloads (windows + linux), external_link is separate
        url_downloads = [d for d in product.downloads if isinstance(d, DownloadItem)]
        assert len(url_downloads) == 2
        assert len(product.external_links) == 1
        assert "steampowered" in product.external_links[0]

    @respx.mock
    async def test_download_item_fields(self, api, tmp_path):
        respx.get("https://www.humblebundle.com/api/v1/order/order123?all_tpkds=true").mock(
            return_value=httpx.Response(200, json=ORDER_JSON)
        )

        order = await api.get_order("order123", tmp_path)
        item = order.products[0].downloads[0]
        assert isinstance(item, DownloadItem)
        assert item.cache_key == "order123:supergame.zip"
        assert item.url == "https://dl.humblebundle.com/supergame.zip?token=abc"
        assert (
            item.local_path == tmp_path / "Humble Indie Bundle 1" / "Super Game" / "supergame.zip"
        )
        assert item.download_type == DownloadType.URL
        assert item.platform == "windows"
        assert item.extension == "zip"
        assert item.md5 == "d41d8cd98f00b204e9800998ecf8427e"

    @respx.mock
    async def test_parses_asmjs_game(self, api, tmp_path):
        respx.get("https://www.humblebundle.com/api/v1/order/order456?all_tpkds=true").mock(
            return_value=httpx.Response(200, json=ORDER_JSON_WITH_ASM)
        )

        order = await api.get_order("order456", tmp_path)
        product = order.products[0]
        assert len(product.downloads) == 1

        game = product.downloads[0]
        assert isinstance(game, AsmJsGame)
        assert game.game_name == "mygame"
        assert game.asm_name == "mygame_asm"
        assert game.order_id == "order456"
        assert game.html_item.cache_key == "order456:mygame.html"
        assert game.html_item.extension == "html"

    @respx.mock
    async def test_raises_on_http_error(self, api, tmp_path):
        respx.get("https://www.humblebundle.com/api/v1/order/bad?all_tpkds=true").mock(
            return_value=httpx.Response(500)
        )
        with pytest.raises(APIError, match="Failed to fetch order"):
            await api.get_order("bad", tmp_path)


class TestGetTroveCatalog:
    @respx.mock
    async def test_fetches_paginated_catalog(self, api, tmp_path):
        respx.get("https://www.humblebundle.com/client/catalog?index=0").mock(
            return_value=httpx.Response(200, json=TROVE_CATALOG_PAGE_1)
        )
        respx.get("https://www.humblebundle.com/client/catalog?index=1").mock(
            return_value=httpx.Response(200, json=TROVE_CATALOG_EMPTY)
        )

        products = await api.get_trove_catalog(tmp_path)
        assert len(products) == 1
        assert products[0].human_name == "Trove Game 1"

    @respx.mock
    async def test_trove_item_fields(self, api, tmp_path):
        respx.get("https://www.humblebundle.com/client/catalog?index=0").mock(
            return_value=httpx.Response(200, json=TROVE_CATALOG_PAGE_1)
        )
        respx.get("https://www.humblebundle.com/client/catalog?index=1").mock(
            return_value=httpx.Response(200, json=TROVE_CATALOG_EMPTY)
        )

        products = await api.get_trove_catalog(tmp_path)
        item = products[0].downloads[0]
        # key is scoped by product title so it matches the path we write to
        assert item.cache_key == "trove:Trove Game 1:trove_game.zip"
        assert item.platform == "windows"
        assert item.uploaded_at == "1715769045"
        assert item.md5 == "abc123"
        assert item.machine_name == "trovegame_windows"
        assert item.local_path == tmp_path / "Humble Trove" / "Trove Game 1" / "trove_game.zip"

    @respx.mock
    async def test_empty_catalog(self, api, tmp_path):
        respx.get("https://www.humblebundle.com/client/catalog?index=0").mock(
            return_value=httpx.Response(200, json=TROVE_CATALOG_EMPTY)
        )
        products = await api.get_trove_catalog(tmp_path)
        assert products == []


class TestGetSignedTroveUrl:
    @respx.mock
    async def test_returns_signed_url(self, api):
        respx.post("https://www.humblebundle.com/api/v1/user/download/sign").mock(
            return_value=httpx.Response(200, json={"signed_url": "https://s3.example.com/signed"})
        )
        url = await api.get_signed_trove_url("machine1", "file.zip")
        assert url == "https://s3.example.com/signed"

    @respx.mock
    async def test_raises_on_unauthorized(self, api):
        respx.post("https://www.humblebundle.com/api/v1/user/download/sign").mock(
            return_value=httpx.Response(200, json={"_errors": "Unauthorized"})
        )
        with pytest.raises(APIError, match="does not have access"):
            await api.get_signed_trove_url("machine1", "file.zip")

    @respx.mock
    async def test_raises_on_http_error(self, api):
        respx.post("https://www.humblebundle.com/api/v1/user/download/sign").mock(
            return_value=httpx.Response(500)
        )
        with pytest.raises(APIError, match="Failed to sign"):
            await api.get_signed_trove_url("machine1", "file.zip")


class TestParseAsmjsManifest:
    def test_parses_manifest(self):
        manifest = HumbleBundleAPI.parse_asmjs_manifest(ASMJS_HTML)
        assert manifest == {
            "game.js": "https://cdn.example.com/game.js",
            "game.data": "https://cdn.example.com/game.data",
        }

    def test_raises_on_missing_data(self):
        with pytest.raises(APIError, match="Could not find"):
            HumbleBundleAPI.parse_asmjs_manifest("<html></html>")


class TestDownloadStream:
    @respx.mock
    async def test_streams_response(self, api):
        respx.get("https://www.humblebundle.com/file.zip").mock(
            return_value=httpx.Response(200, content=b"file content")
        )
        async with api.download_stream("/file.zip") as response:
            assert response.status_code == 200


class TestDuplicateBasenames:
    """download_struct may list several entries sharing one URL basename."""

    def _product(self, structs):
        return {
            "human_name": "Some Book",
            "downloads": [{"platform": "video", "download_struct": structs}],
        }

    def test_same_basename_different_md5_gets_distinct_key_and_path(self, api, tmp_path):
        product = self._product(
            [
                {"name": "ZIP", "md5": "aaa", "url": {"web": "https://d/x/book.zip"}},
                {"name": "Download", "md5": "bbb", "url": {"web": "https://d/y/book.zip"}},
            ]
        )
        result = api._parse_product("ORD1", "Bundle", product, tmp_path)

        assert len(result.downloads) == 2
        keys = [d.cache_key for d in result.downloads]
        paths = [d.local_path for d in result.downloads]
        assert len(set(keys)) == 2, "colliding cache keys"
        assert len(set(paths)) == 2, "colliding local paths"

        # first occurrence keeps the bare name, so existing caches stay valid
        assert keys[0] == "ORD1:book.zip"
        assert paths[0].name == "book.zip"
        # second is disambiguated by Humble's own label
        assert keys[1] == "ORD1:Download:book.zip"
        assert paths[1].name == "book [Download].zip"

    def test_identical_entries_are_deduplicated(self, api, tmp_path):
        product = self._product(
            [
                {"name": "ZIP", "md5": "same", "url": {"web": "https://d/x/book.zip"}},
                {"name": "ZIP", "md5": "same", "url": {"web": "https://d/x/book.zip"}},
            ]
        )
        result = api._parse_product("ORD1", "Bundle", product, tmp_path)
        assert len(result.downloads) == 1
        assert result.downloads[0].cache_key == "ORD1:book.zip"

    def test_distinct_basenames_are_untouched(self, api, tmp_path):
        product = self._product(
            [
                {"name": "PDF", "md5": "a", "url": {"web": "https://d/x/book.pdf"}},
                {"name": "EPUB", "md5": "b", "url": {"web": "https://d/x/book.epub"}},
            ]
        )
        result = api._parse_product("ORD1", "Bundle", product, tmp_path)
        assert [d.cache_key for d in result.downloads] == [
            "ORD1:book.pdf",
            "ORD1:book.epub",
        ]
        assert [d.local_path.name for d in result.downloads] == ["book.pdf", "book.epub"]

    def test_extensionless_duplicate_is_still_disambiguated(self, api, tmp_path):
        product = self._product(
            [
                {"name": "A", "md5": "a", "url": {"web": "https://d/x/README"}},
                {"name": "B", "md5": "b", "url": {"web": "https://d/y/README"}},
            ]
        )
        result = api._parse_product("ORD1", "Bundle", product, tmp_path)
        names = [d.local_path.name for d in result.downloads]
        assert names == ["README", "README [B]"]
