# Change log


## 0.6.0

- **Fix**: files whose upstream MD5 is stale were downloaded correctly, rejected,
  and silently deleted. Humble serves newer editions of some files without
  refreshing `file_size`/`md5` in its order API -- 484 of 4174 files (12%) in
  one reference library. The upstream hash is now advisory: a mismatch warns and
  keeps the file, recording the real hash as `file_md5`. The `DownloadError`
  handler also deleted without logging, making the loss invisible.
- **Fix**: `cache_key` and `local_path` were both derived from the URL basename,
  so two entries in one product sharing a basename collapsed onto one slot and
  streamed onto the same file concurrently. Identical entries are now dropped,
  and a repeated basename with a different md5 is suffixed with Humble's own
  `name` label. The first occurrence keeps its bare name, so existing caches
  stay valid.
- **Fix**: two different orders can resolve to one path (the same bundle bought
  twice), which no parse-time dedupe can catch. The engine now claims a path for
  the duration of a run so exactly one task writes it.
- **Fix**: non-200 responses logged at `debug`, invisible without `--verbose`.
  Now `warning`.
- **New**: transient HTTP statuses (408, 425, 429, 5xx) are retried instead of
  being a permanent give-up.
- **New**: end-of-run summary (`N downloaded  N skipped  N failed`) and a
  non-zero exit code when anything fails. Previously a run that dropped 484
  files still exited 0 with an empty error log.
- **Breaking**: Trove cache keys are now scoped by product title
  (`trove:{title}:{file}`) so they match the path written to. Existing Trove
  cache entries are orphaned and will be re-checked once.
- **Security**: floor `anyio>=4.14.2` (CVE-2026-63374, critical -- TLS
  certificate spoofing via IDNA 2003 host name encoding in `TLSStream`, which
  httpcore's async backend routes every HTTPS request through) and `idna>=3.15`
  (CVE-2026-45409). Both are transitive via httpx.
- See `KNOWN_ISSUES.md` for the full diagnosis of both data-loss defects,
  including two incorrect diagnoses made along the way.


## 0.5.1

- **Rebrand**: project renamed to `humble-dl`. Distribution name on PyPI is now
  `humble-dl` and the import name is `humble_dl`. The CLI command remains `hbd`.
- Fork now maintained by Felipe Tadeu under
  [github.com/timsleeper/humble-dl](https://github.com/timsleeper/humble-dl).
- Released to PyPI for the first time under the new name.
- Docker image published to `ghcr.io/timsleeper/humble-dl`.
- Migrated CI from GitLab to GitHub Actions; releases use PyPI Trusted
  Publishing (no API token in repo).


## 0.5.0

- **Breaking**: Complete rewrite of the codebase
- **New**: Automatic browser cookie detection via rookiepy (`--auto` / `--browser` flags)
- **New**: Parallel async downloads with configurable concurrency (`--concurrent` flag)
- **New**: Rich progress bars with download speed and ETA per file
- **New**: Typer-based CLI with improved help text and validation
- **New**: Modular architecture (auth, api, cache, downloader, filters)
- **Fix**: Trove update check used AND instead of OR for uploaded_at/md5 comparison
- **Fix**: Undefined variable reference in asm.js error handler
- **Fix**: `finally: return True` swallowing exceptions in download handler
- **Fix**: Progress bar print statements leaking outside progress_bar flag
- Migrated from Poetry to uv for package management
- Migrated from requests (sync) to httpx (async)
- Migrated from argparse to typer + rich
- Replaced `--progress` flag with always-on Rich progress display
- Dropped Python < 3.10 support


## 0.4.3

- Added support for asm games ([#75](https://github.com/xtream1101/humblebundle-downloader/pull/75))


## 0.4.2

- Added public docker image
- New version just to make sure the updated ci/cd pipeline is working, no code changes in this release


## 0.4.1

- Fixed crash when missing cli args ([#48](https://github.com/xtream1101/humblebundle-downloader/pull/48))
- Updated the Trove url ([#59](https://github.com/xtream1101/humblebundle-downloader/pull/59))
- Using [pre-commit](https://pre-commit.com/) hooks for formatting and linting
- Moved from setuptools to poetry for packaging


## 0.4.0

- Deprecate the `download` argument. It is no longer needed since that is the only action that can be taken


## 0.3.4

- Merged in [PR 35](https://github.com/xtream1101/humblebundle-downloader/pull/35) to fix some trove games not downloading


## 0.3.3

- Fixed crashing when file is missing on humblebundle
- Updated cookie info in readme
    - Supports passing in the cookie value of `_simpleauth_sess` by using `--session-auth`


## 0.3.1

- Added support for netscape cookies


## 0.3.0

- pip install now requires python version 3.4+
- `--trove` will only download trove products, nothing else
- Filtering flags now work when downloading trove content


## 0.2.2

- Confirm the download is complete by checking the expected size to what downloaded
- Fixed the platform filter


## 0.2.1

- Fixed include & exclude logic being switched in v0.2.0


## 0.2.0

- Added **Humble Trove** support _(`--trove` to also check/download trove content)_
- Now by default only new content is downloaded. Use `--update` to also check for updated content


## 0.1.3

- Fixed re-downloading for real this time
    - Only use the url last modified time as the check for new versions


## 0.1.2

- Stop using md5 & sha1 hashes to check if file is unique (was creating duplicate downloads of the same file)
- Strip periods from end of directory & file names
- Rename older versions of a file before download the new one


## 0.1.1

- Delete failed downloaded files


## 0.1.0

- Filename saved is now the original name of the file
- key used in cache is different due to changing the file name
    - _this may result in duplicate downloads if you have run the older version_
- Support for downloading a single Bundle/Purchase by using the
  flag `-k` or `--key` and getting the key from the url of a purchase


## 0.0.8

- gen-cookies now works with SSO feature and 2FA logins
- Added `--include` & `--exclude` cli args to filter file types


## 0.0.7

- Replace `:` with `-` in filenames
- Ignore items that do not have a web url


## 0.0.6

- Started change log
- Added more detail to readme
- Removed the use of f-strings to support more python versions
- Fixed bug where folders and files were only a single letter
