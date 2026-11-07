import os
from pathlib import Path


_ALLOWED_CHARS = frozenset(" _.-[]")


def fs_path(path: Path) -> Path:
    r"""Filesystem-access form of ``path`` that is safe for long paths on Windows.

    Windows' default ``MAX_PATH`` is 260 characters; a deep library tree
    (bundle / product / long-filename) easily exceeds that and ordinary opens
    fail with ``FileNotFoundError``/``WinError 3``. Prefixing an absolute,
    normalised path with the ``\\?\`` extended-length marker lifts the limit.

    This is a no-op on non-Windows platforms and for already-prefixed paths.
    Use the result only to open/create/stat files -- keep the original path for
    display and for recording in the cache (``\\?\`` paths look alien there).
    """
    if os.name != "nt":
        return path
    raw = os.path.abspath(str(path))
    if raw.startswith("\\\\?\\"):
        return path
    if raw.startswith("\\\\"):
        # UNC share: \\server\share\... -> \\?\UNC\server\share\...
        return Path("\\\\?\\UNC\\" + raw[2:])
    return Path("\\\\?\\" + raw)


def clean_name(dirty_str: str) -> str:
    """Sanitize a string for use as a filename or directory name.

    Replaces + with _, : with " -", strips disallowed characters,
    and strips trailing dots.
    """
    clean = []
    for c in dirty_str.replace("+", "_").replace(":", " -"):
        if c.isalnum() or c in _ALLOWED_CHARS:
            clean.append(c)
    return "".join(clean).strip().rstrip(".")


def rename_old_file(local_path: Path, append_str: str) -> Path | None:
    """If local_path exists, rename it by inserting append_str before the extension.

    Example: game.zip -> game_2024-01-15.zip

    Returns the new path if renamed, None if file didn't exist.
    """
    src = fs_path(local_path)
    if not src.is_file():
        return None
    new_name = f"{local_path.stem}_{append_str}{local_path.suffix}"
    new_path = local_path.with_name(new_name)
    # replace(), not rename(): on Windows os.rename raises FileExistsError
    # when the destination already exists (e.g. a prior same-day backup).
    src.replace(fs_path(new_path))
    return new_path
