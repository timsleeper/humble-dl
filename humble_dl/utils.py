from pathlib import Path


_ALLOWED_CHARS = frozenset(" _.-[]")


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
    if not local_path.is_file():
        return None
    new_name = f"{local_path.stem}_{append_str}{local_path.suffix}"
    new_path = local_path.with_name(new_name)
    local_path.rename(new_path)
    return new_path
