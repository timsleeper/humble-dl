class HBDError(Exception):
    """Base exception for humble-dl."""


class AuthError(HBDError):
    """Authentication failed or no valid cookies found."""


class APIError(HBDError):
    """Humble Bundle API request failed."""


class DownloadError(HBDError):
    """File download failed or was incomplete."""
