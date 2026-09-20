# Known Issues

> **Both issues below are FIXED as of 2026-09-20.** The write-ups are kept in
> full because the diagnosis took two wrong turns, and the reasoning is worth
> more than the conclusion. See "Resolution" under each.

## 1. Cache-key and local-path collision causes silent file loss

**Status:** FIXED 2026-09-20.
**Severity:** high (silent data loss, self-concealing).

### Summary

`cache_key` and `local_path` are both derived from the URL basename, so two
*different* files within the same order that happen to share a basename collapse
onto a single cache entry and a single path on disk. They are then downloaded
concurrently into the same file, the MD5 check fails on the mixed result, the
file is deleted, and the cache is left marking it as successfully downloaded.

The file is gone and every subsequent run skips it.

### Root cause

In `humble_dl/api.py:_parse_product`:

```python
product_folder = library_path / bundle_title / product_title   # :149
url_filename = url.split("?")[0].split("/")[-1]                # :160
cache_key = f"{order_id}:{url_filename}"                       # :161
local_path=product_folder / url_filename,                      # :166
```

Nothing in either the key or the path distinguishes two entries that share
`url_filename` within one `order_id` + product. The `download_struct` list can
legitimately contain multiple entries with the same basename but different
`file_size` and `md5`.

### Failure sequence

1. Two `DownloadItem`s are built with an identical `cache_key` and `local_path`.
2. Both are dispatched by `_process_order`'s `asyncio.gather` and both pass the
   cache check at `downloader.py:115` (no entry yet).
3. Both open `local_path` with mode `"wb"` and write concurrently from offset 0,
   interleaving two different byte streams.
4. Task A finishes, its MD5 matches nothing meaningful but it may complete first
   and write the cache entry at `downloader.py:231`.
5. Task B's MD5 check fails (`downloader.py:175`), raising `DownloadError`. The
   handler at `downloader.py:182-185` unlinks the file and re-raises.
6. The exception is swallowed by `asyncio.gather(..., return_exceptions=True)`
   in `_process_order`, so nothing is logged at error level.

Net result: cache entry present, file absent, exit code 0, empty error log.

### Why it hides itself

`_download_item` skips any item that already has a cache entry:

```python
if cached is not None and not self._update:   # downloader.py:115
    return DownloadStatus.SKIPPED
```

Since step 4 wrote an entry, a plain re-run never re-fetches the file. Recovery
requires `--update` or deleting the poisoned key. Note that `--update` alone does
not fix it: both variants still resolve to the same path, so the race and the MD5
mismatch simply recur.

### Observed impact

Scan of all 165 orders: **9 colliding cache keys out of 4174**.

Eight are exact duplicates (same `file_size`, same `md5` — the same file listed
twice in one order). Those are benign: both writers emit identical bytes to the
same offsets, so the result is correct. They only waste bandwidth.

One is a genuine collision between two different files:

```
order   N2GZkVtGSR8ZkcRZ
bundle  Humble Book Bundle: iOS & Android Mobile Development by Packt
product SwiftUI - Build Beautiful, Robust, Apps
file    swiftui_buildbeautifulrobustapps.zip

  variant A: 13167344003 bytes (12.26 GB)  md5 6e3f57c31419d09115ea0790e12aa65f
  variant B:  1026397571 bytes ( 0.96 GB)  md5 5668074037a21c9d6a565361035fde6e
```

Confirmed lost on disk: the product directory exists and is empty, while
`.cache.json` holds an entry claiming the 12.26 GB variant completed.

### Follow-up 2026-09-20: both variants now serve identical bytes

Fetching both entries separately, to distinct filenames, produced an unexpected
result:

```
[ZIP]      declared 13,167,344,003  got 13,167,344,003  md5 6e3f57c3... MATCH
[Download] declared  1,026,397,571  got 13,167,344,003  md5 6e3f57c3... MISMATCH
```

Both URLs return the **same 12.26 GB file**. Confirmed with `md5sum` on disk:
identical hash, identical size. The 0.96 GB variant no longer exists upstream;
its `download_struct` entry still advertises stale `file_size`/`md5`, which is
issue #2 wearing a different hat.

Consequences:

- The *current* cost of this collision is a duplicate download of the same
  bytes, not divergent content. Deduplicating `download_struct` by `md5` at
  parse time would not catch this, since the declared md5s differ while the
  payloads do not.
- The original data loss was real all the same: under the old delete-on-mismatch
  behaviour, the second task deleted the file the first had correctly stored.
  Issue #2's fix removes that failure mode.
- The collision itself remains an unfixed latent correctness risk. Nothing
  guarantees Humble will keep serving identical bytes for two entries it
  describes differently.

Resolved in `/data` by keeping one copy under the original filename, which the
existing cache entry already describes accurately (md5 `6e3f57c3...`,
13,167,344,003 bytes), and deleting the verified-identical duplicate. No cache
editing was required.

### Proposed fix

1. Disambiguate `cache_key` — include the `md5` (or a short hash of the full URL
   path) rather than the basename alone.
2. Disambiguate `local_path` — when a basename repeats within a product, suffix
   it (e.g. `name.md5prefix.zip`) so distinct files cannot share a slot.
3. Consider making the collision structurally impossible instead of merely
   unlikely: deduplicate `download_struct` entries by `md5` at parse time, which
   also removes the 8 wasteful duplicate downloads.
4. Surface swallowed failures — `_process_order` and `download_library` use
   `return_exceptions=True` and discard the results. Aggregate them and print a
   end-of-run summary so a failure this shape is visible.

Apply the same treatment to the Trove key at `humble_dl/api.py:219`
(`f"trove:{web_name}"`), which has the identical weakness across products.

### Regression test to add

The suite has no coverage for duplicate basenames within one order. Add a case
where `download_struct` contains two entries sharing a basename with differing
`md5`, and assert that two distinct cache keys and two distinct paths result.

### Recovery for the existing library — DONE 2026-09-20

Carried out, though not as originally planned. Because both variants turned out
to serve identical bytes (see follow-up above), no cache surgery was needed:

1. Both variants fetched to distinct `[ZIP]` / `[Download]` filenames.
2. Verified byte-identical on disk with `md5sum` (`6e3f57c3...`, 13,167,344,003
   bytes each).
3. Kept one copy under the original filename `swiftui_buildbeautifulrobustapps.zip`
   — which the existing cache entry already described accurately — and deleted
   the duplicate, reclaiming 13.17 GB.

The poisoned cache key did **not** need deleting: once the real file sits at the
path the entry names, the entry is correct. The underlying collision bug remains
open.


---

## 2. Stale upstream MD5 metadata causes 484 files to be silently deleted

**Status:** FIXED 2026-09-20.
**Severity:** critical (12% of the library is undownloadable, with no error output).

> **Correction:** an earlier revision of this document blamed non-200 responses
> and signed-URL expiry. That was wrong — it was reached by elimination and
> missed a fourth, unlogged failure path. Direct testing disproved it: the
> requests all return **HTTP 200** and transfer completely. The real cause is
> below.

### Summary

484 of 4174 files (8.21 GB, 62 orders) cannot be downloaded at all. Every
attempt succeeds at the HTTP level, then the file is deleted and the error is
discarded. The run exits 0 with an empty error log, and re-running never helps
because the failure is deterministic, not transient.

**Humble serves file bytes that do not match the `file_size` and `md5` its own
order API declares for them.** The tool treats its MD5 check as authoritative,
so it rejects and deletes perfectly good files.

### Evidence

Downloading directly, bypassing the tool (12-file random sample, all <15 MB):

```
bookofpf3rdedition.pdf        exp=5388075   got=6390214   magic=%PDF
appliedcomputational....epub  exp=9118842   got=9842774   magic=PK\x03\x04
bookofkubernetes.pdf          exp=6211034   got=4819057   magic=%PDF
mysqlcrashcourse.mobi         exp=5983582   got=6479571   magic=MOBI hdr
codecraft.mobi                exp=15707153  got=7960467   magic=MOBI hdr
robustpython.epub             exp=5347688   got=5341995   magic=PK\x03\x04
...
summary: 5 pdf, 5 epub, 2 mobi -- 12/12 size AND md5 mismatch
```

Every response was HTTP 200, `content-length` agreed with the bytes received,
and every payload carried a valid file signature. The served files are genuine
and well-formed — they are simply *newer* than the metadata, consistent with
Humble replacing books with updated editions without refreshing the order JSON.

Note the split: 3690 files (88%) have accurate metadata and downloaded fine;
484 (12%) have stale metadata and are permanently rejected.

### Root cause: the fourth, unlogged failure path

`_do_download` has four failure exits, not three. The MD5 branch is the only one
that produces no log output whatsoever:

| Path | Log call | Visible? |
|---|---|---|
| non-200 response | `logger.debug(...)` | only with `--verbose` |
| retries exhausted | `logger.error(...)` | yes |
| unexpected exception | `logger.exception(...)` | yes |
| **MD5 mismatch** | **none** | **never** |

```python
if item.md5 and md5_hash.hexdigest() != item.md5:      # downloader.py:174-178
    raise DownloadError(...)
...
except DownloadError:                                   # downloader.py:182-185
    if item.local_path.exists():
        item.local_path.unlink()
    raise
```

`DownloadError` carries a descriptive message that is never logged. The re-raise
lands in `asyncio.gather(..., return_exceptions=True)` in `_process_order`, whose
results are discarded. Net effect: file downloaded, file deleted, exception
swallowed, no cache entry, exit code 0.

A retry loop cannot fix this. Confirmed empirically: a second full pass
downloaded 0 files and left MISSING at 484, producing a log containing zero
`downloader.py` lines.

### Proposed fix

1. **Never delete on MD5 mismatch without logging.** At minimum
   `logger.error(str(e))` before the unlink.
2. **Treat upstream MD5 as advisory, not authoritative.** It is demonstrably
   wrong for 12% of this library. On mismatch: keep the file, log a warning,
   and record the *actual* md5 in the cache. Corruption detection should come
   from `content-length` agreement plus the retry path, which already catches
   truncation (`Incomplete download`).
3. Optionally gate strict behaviour behind `--strict-md5` for users who want
   the current semantics.
4. Aggregate `DownloadStatus` results and print an end-of-run summary with a
   non-zero exit code on failure. This would have surfaced the problem on day
   one instead of after a full 8-hour run.

### Regression test to add

Serve a body whose md5 differs from `DownloadItem.md5` and assert the file is
retained, a warning is logged, and a cache entry with the real md5 is written.


---

## Resolution (2026-09-20)

### Issue #1 — collisions

`_parse_product` now tracks basenames within a product:

- identical entries (same basename *and* md5) are dropped — this removed the 8
  duplicate downloads;
- a repeated basename with a *different* md5 is suffixed with Humble's own
  `name` label (`book [Download].zip`) and given a scoped key
  (`{order}:{label}:{file}`);
- the **first** occurrence keeps its bare name and key, so existing caches stay
  valid. Verified against the live library: 4175 items, 4175 distinct keys,
  **0 orphaned cache entries**.

`_parse_trove_product` keys are now scoped by product title
(`trove:{title}:{file}`), matching the path they are written to. This
invalidates existing Trove cache entries — a one-time re-check for Trove users.

A second collision surfaced during validation and is also fixed: two *different
orders* can resolve to the same path (the same bundle bought twice), which no
parse-time dedupe can catch since the keys legitimately differ. `DownloadEngine`
now claims a path for the duration of a run, so exactly one task writes it
(194 such paths exist in the reference library).

### Issue #2 — stale MD5

- MD5 mismatch logs a warning and **keeps** the file; the real hash goes to the
  cache as `file_md5`, with the upstream claim retained as `md5`.
- `except DownloadError` logs before unlinking. No silent deletes remain.
- Non-200 is now `logger.warning`, visible by default.
- Transient statuses (408, 425, 429, 500, 502, 503, 504) route into the retry
  path instead of being a permanent give-up.
- Outcomes are counted rather than discarded. `download_library` /
  `download_trove` return a `Counter`, exceptions that `gather()` would swallow
  are logged and counted, and the CLI prints
  `N downloaded  N skipped  N failed` and **exits non-zero** on failure.

### Not done

- Refreshing a signed URL before retrying a 403, the way the Trove path signs
  immediately before transfer. Purchase URLs are still captured once per run.
  This was never confirmed to be a real failure mode — it was the first,
  incorrect diagnosis of issue #2 — so it is left alone rather than fixed
  speculatively.

### Test coverage added

11 tests: duplicate basenames (distinct/dedup/untouched/extensionless), transient
status retry (503, 429, exhaustion, 404-no-retry), outcome accounting, and path
claiming. Suite: **203 passing**.
