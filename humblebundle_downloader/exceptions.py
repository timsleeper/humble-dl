class HBDError(Exception):
    """Base exception for humblebundle-downloader."""


class AuthError(HBDError):
    """Authentication failed or no valid cookies found."""


class APIError(HBDError):
    """Humble Bundle API request failed."""


class DownloadError(HBDError):
    """File download failed or was incomplete."""
