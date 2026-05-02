import asyncio
import hashlib
import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from .auth import create_client
from .exceptions import AuthError

console = Console()

app = typer.Typer(
    name="hbd",
    help="Download your Humble Bundle library.",
    add_completion=False,
    rich_markup_mode="rich",
)


@app.command()
def download(
    library_path: Path = typer.Option(
        ...,
        "--library-path",
        "-l",
        help="Folder to download all content to.",
    ),
    cookie_file: Path | None = typer.Option(
        None,
        "--cookie-file",
        "-c",
        help="Path to Netscape cookie file.",
        exists=True,
    ),
    session_auth: str | None = typer.Option(
        None,
        "--session-auth",
        "-s",
        help="Value of _simpleauth_sess cookie (wrap in quotes).",
    ),
    browser: str | None = typer.Option(
        None,
        "--browser",
        "-b",
        help="Browser to extract cookies from (chrome, firefox, edge, brave, etc.).",
    ),
    auto_cookies: bool = typer.Option(
        False,
        "--auto",
        "-a",
        help="Automatically detect cookies from any browser.",
    ),
    trove: bool = typer.Option(
        False,
        "--trove",
        "-t",
        help="Only download Humble Trove content.",
    ),
    update: bool = typer.Option(
        False,
        "--update",
        "-u",
        help="Check for updated versions of already-downloaded files.",
    ),
    platform: list[str] | None = typer.Option(
        None,
        "--platform",
        "-p",
        help="Only download content for these platforms (e.g. ebook, video).",
    ),
    include: list[str] | None = typer.Option(
        None,
        "--include",
        "-i",
        help="Only download files with these extensions.",
    ),
    exclude: list[str] | None = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Skip files with these extensions.",
    ),
    keys: list[str] | None = typer.Option(
        None,
        "--keys",
        "-k",
        help="Only download specific purchase keys.",
    ),
    concurrent: int = typer.Option(
        5,
        "--concurrent",
        "-n",
        help="Maximum number of parallel downloads.",
        min=1,
        max=20,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging.",
    ),
) -> None:
    """Download your Humble Bundle library."""
    # Validate mutually exclusive auth options
    auth_options = [
        cookie_file is not None,
        session_auth is not None,
        browser is not None,
        auto_cookies,
    ]
    if sum(auth_options) == 0:
        console.print(
            "[red]Error:[/] One of --cookie-file, --session-auth, "
            "--browser, or --auto is required."
        )
        raise typer.Exit(code=2)
    if sum(auth_options) > 1:
        console.print(
            "[red]Error:[/] Only one of --cookie-file, --session-auth, "
            "--browser, or --auto may be specified."
        )
        raise typer.Exit(code=2)

    # Validate mutually exclusive filter options
    if include and exclude:
        console.print("[red]Error:[/] --include and --exclude cannot both be set.")
        raise typer.Exit(code=2)

    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    asyncio.run(
        _run(
            library_path=library_path,
            cookie_file=cookie_file,
            session_auth=session_auth,
            browser=browser,
            auto_cookies=auto_cookies,
            trove=trove,
            update=update,
            platform_include=platform,
            ext_include=include,
            ext_exclude=exclude,
            purchase_keys=keys,
            concurrent=concurrent,
        )
    )


async def _run(
    library_path: Path,
    cookie_file: Path | None,
    session_auth: str | None,
    browser: str | None,
    auto_cookies: bool,
    trove: bool,
    update: bool,
    platform_include: list[str] | None,
    ext_include: list[str] | None,
    ext_exclude: list[str] | None,
    purchase_keys: list[str] | None,
    concurrent: int,
) -> None:
    """Async entry point wired by the CLI."""
    # Lazy imports to avoid circular deps and speed up --help
    from .api import HumbleBundleAPI
    from .cache import DownloadCache
    from .downloader import DownloadEngine

    try:
        client = await create_client(
            cookie_file=cookie_file,
            session_auth=session_auth,
            browser=browser,
            auto_detect=auto_cookies,
        )
    except AuthError as e:
        console.print(f"[red]Authentication error:[/] {e}")
        raise typer.Exit(code=1)

    async with client:
        api = HumbleBundleAPI(client)
        cache = DownloadCache(library_path)
        await cache.load()

        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            engine = DownloadEngine(
                api=api,
                cache=cache,
                library_path=library_path,
                max_concurrent=concurrent,
                update=update,
                ext_include=ext_include,
                ext_exclude=ext_exclude,
                platform_include=platform_include,
                progress=progress,
            )

            if trove:
                await engine.download_trove()
            else:
                await engine.download_library(purchase_keys=purchase_keys)

        await cache.flush()


@app.command()
def verify(
    library_path: Path = typer.Option(
        ...,
        "--library-path",
        "-l",
        help="Folder where content was downloaded.",
    ),
) -> None:
    """Verify integrity of downloaded files using cached MD5 hashes and file sizes."""
    cache_file = library_path / ".cache.json"
    if not cache_file.exists():
        console.print("[red]Error:[/] No .cache.json found. Nothing to verify.")
        raise typer.Exit(code=1)

    data = json.loads(cache_file.read_text())

    missing = []
    size_mismatch = []
    md5_mismatch = []
    ok = 0
    skipped = 0

    entries_with_path = [
        (key, entry) for key, entry in data.items() if "local_path" in entry
    ]

    if not entries_with_path:
        console.print(
            "[yellow]No verification data found.[/] "
            "Re-download files to populate file_md5/file_size in the cache."
        )
        raise typer.Exit(code=1)

    skipped = len(data) - len(entries_with_path)

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=console,
    ) as progress:
        task = progress.add_task("Verifying files...", total=len(entries_with_path))

        for key, entry in entries_with_path:
            local_path = Path(entry["local_path"])
            progress.update(task, description=local_path.name)

            if not local_path.exists():
                missing.append(key)
                progress.advance(task)
                continue

            expected_size = entry.get("file_size")
            if expected_size is not None:
                actual_size = local_path.stat().st_size
                if actual_size != expected_size:
                    size_mismatch.append((key, expected_size, actual_size))
                    progress.advance(task)
                    continue

            expected_md5 = entry.get("file_md5")
            if expected_md5 is not None:
                md5_hash = hashlib.md5()
                with open(local_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        md5_hash.update(chunk)
                if md5_hash.hexdigest() != expected_md5:
                    md5_mismatch.append((key, expected_md5, md5_hash.hexdigest()))
                    progress.advance(task)
                    continue

            ok += 1
            progress.advance(task)

    console.print()

    if missing or size_mismatch or md5_mismatch:
        if missing:
            table = Table(title="Missing Files", show_lines=False)
            table.add_column("Cache Key", style="red")
            for key in missing:
                table.add_row(key)
            console.print(table)
            console.print()

        if size_mismatch:
            table = Table(title="Size Mismatch", show_lines=False)
            table.add_column("Cache Key", style="yellow")
            table.add_column("Expected", justify="right")
            table.add_column("Actual", justify="right")
            for key, expected, actual in size_mismatch:
                table.add_row(key, str(expected), str(actual))
            console.print(table)
            console.print()

        if md5_mismatch:
            table = Table(title="MD5 Mismatch", show_lines=False)
            table.add_column("Cache Key", style="yellow")
            table.add_column("Expected MD5")
            table.add_column("Actual MD5")
            for key, expected, actual in md5_mismatch:
                table.add_row(key, expected, actual)
            console.print(table)
            console.print()

    problems = len(missing) + len(size_mismatch) + len(md5_mismatch)
    console.print(
        f"[green]{ok} OK[/]  "
        f"[red]{problems} failed[/]  "
        f"[dim]{skipped} skipped (no verification data)[/]"
    )

    if problems > 0:
        raise typer.Exit(code=1)
