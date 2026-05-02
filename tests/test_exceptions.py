from humble_dl.exceptions import (
    APIError,
    AuthError,
    DownloadError,
    HBDError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_hbd_error(self):
        assert issubclass(AuthError, HBDError)
        assert issubclass(APIError, HBDError)
        assert issubclass(DownloadError, HBDError)

    def test_all_inherit_from_exception(self):
        assert issubclass(HBDError, Exception)
        assert issubclass(AuthError, Exception)
        assert issubclass(APIError, Exception)
        assert issubclass(DownloadError, Exception)

    def test_catch_specific_with_base(self):
        with __import__("pytest").raises(HBDError):
            raise AuthError("bad cookie")

        with __import__("pytest").raises(HBDError):
            raise APIError("request failed")

        with __import__("pytest").raises(HBDError):
            raise DownloadError("incomplete")

    def test_message_preserved(self):
        err = AuthError("no cookies found")
        assert str(err) == "no cookies found"

    def test_distinct_types(self):
        # Each can be caught independently
        try:
            raise AuthError("auth")
        except APIError:
            assert False, "AuthError should not be caught by APIError"
        except AuthError:
            pass
