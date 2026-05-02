def should_download_ext(
    ext: str,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> bool:
    """Check if a file extension should be downloaded.

    Args:
        ext: File extension (without dot), e.g. "pdf".
        include: If non-empty, only these extensions are allowed.
        exclude: If non-empty, these extensions are blocked.
        include takes priority over exclude.

    Returns:
        True if the file should be downloaded.
    """
    ext = ext.lower()
    if include:
        return ext in [e.lower() for e in include]
    if exclude:
        return ext not in [e.lower() for e in exclude]
    return True


def should_download_platform(
    platform: str,
    platform_include: list[str] | None = None,
) -> bool:
    """Check if a platform should be downloaded.

    Args:
        platform: Platform name, e.g. "windows", "ebook".
        platform_include: If non-empty, only these platforms are allowed.
                         None or empty or containing "all" means all platforms.

    Returns:
        True if the platform should be downloaded.
    """
    if not platform_include or "all" in [p.lower() for p in platform_include]:
        return True
    return platform.lower() in [p.lower() for p in platform_include]


def get_file_ext(filename: str) -> str:
    """Extract extension from filename. Returns lowercase, no dot."""
    parts = filename.rsplit(".", 1)
    return parts[-1].lower() if len(parts) > 1 else ""


def should_download_file(
    filename: str,
    ext_include: list[str] | None = None,
    ext_exclude: list[str] | None = None,
) -> bool:
    """Check filename extension against include/exclude filter lists."""
    ext = get_file_ext(filename)
    return should_download_ext(ext, include=ext_include, exclude=ext_exclude)
