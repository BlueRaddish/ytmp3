# October 28, 2026 optimization ledger

Scope: the source-search/website-preview build, compared with `9bd03c9`.
Resource changes are in `077d12c`; persisted-data recovery is in `238a71a`.
This is a local debug iteration, with the public version/feed unchanged at 1.0.0.

## Workload and method

`tests/measure_efficiency.py` runs the real authenticated Python app and shared
web UI in a fresh, isolated headless Edge process on Windows. The workload has
5,000 synthetic tracks, a 1,000-item queue, 20 identical library refreshes, eight
100-row list renders, three seconds of visible paused playback and three hidden,
400 actual own-tone MP3 files rotated through 20 scans, and 20 identical searches.
Native playback and the upstream search extractor are controlled adapters.
The search adapter deliberately takes 10 ms; its times are not YouTube latency.

Three successful runs per revision use measurement version 2. Files are
`before-{1,2,3}.json` and `after-{2,3,4}.json`. Baselines and candidates were
interleaved; one candidate timed out under Windows commit pressure before the
final three successful candidates. Earlier version-1 exploratory results are
retained separately and excluded. The busy 16 GB PC was not isolated. No user
applications were closed and no working-set trimming was used.

Workload acceptance budgets: app import plus navigation to usable library below
2 seconds (excluding browser launch); a 100-row list action below 100 ms; initial
library rendering bounded to 100 rows; unchanged snapshot persistence at most
once per minute; no hidden native playback bridge polling; no removed paths in
the tag cache; search cache at most 16 queries for 60 seconds, with at most two
simultaneous upstream extractors. These are scoped budgets, not universal limits.

## Measured results

Each latency is the median of three per-run medians, with the range of those
medians. Counts are per run unless stated otherwise.

| Operation/resource | Before | After |
|---|---:|---:|
| Unchanged 5,000-track refresh | 9.65 ms (8.85–10.70) | 4.30 ms (3.65–5.40) |
| Snapshot writes / 20 unchanged refreshes | 20 | 0 |
| UTF-16 snapshot payload presented for those writes | 41,981,240 bytes | 0 |
| Hidden bridge calls / 3 seconds | 6–7 | 0 |
| Visible paused player redraws / 3 seconds | 6 | 0 |
| Stale tag entries after all 400 files removed | 400 | 0 |
| Retained traced allocations after tag turnover | 192,144 B (191,072–192,624) | 5,488 B (5,440–5,512) |
| Extractor runs / 20 identical searches | 20 | 1 |
| App import + page readiness | 741 ms (733–747) | 861 ms (687–1,062) |
| Render 100 list rows | 36.65 ms (34.10–38.00) | 41.30 ms (38.35–56.75) |

The refresh change preserves the existing track index when content is unchanged
and reuses its serialization for persistence. Changed libraries persist
immediately; unchanged snapshots refresh their saved timestamp at most once per
minute. A sudden process exit can therefore leave that freshness timestamp up to
one minute behind; the cached tracks remain available and launch still rescans.

The playback timer now has explicit ownership, stops on hidden/page teardown,
and refreshes immediately on resume. Unchanged bridge payloads skip parsing and
player DOM work. Native Media3 playback remains independent of the UI timer.

Tag-cache pruning follows completed library scans. Search results are copied on
return, errors are retryable, and expired queries are discarded. The 60-second
search cache trades up-to-one-minute freshness for avoiding duplicate extraction;
it does not cache failures. Extractor count is not a literal HTTP-request count.

## Resource attribution and checked non-findings

- **RAM/commit:** owned harness/server/browser tree peak private memory was
  546.5 MiB (542.8–559.2) before and 521.6 MiB (516.1–521.6) after; working set
  was 801.5 MiB (785.6–829.5) and 781.9 MiB (777.5–782.1). These include browser
  and profiler noise and are observations, not a promised app-wide RAM saving.
  Uncollected browser heap was 17.41 versus 8.88 MiB at the sampled point; no
  forced GC means this is not a retained-heap measurement. The tag-cache trace
  above is the direct retention evidence. No Android native-memory claim.
- **CPU/concurrency:** visible paused process-tree CPU over three seconds was
  3.92 s (3.61–4.06) versus 1.23 s (0.78–3.06); hidden CPU ranges overlapped at
  0.73–0.89 s versus 0.58–0.86 s. Do not infer a precise CPU percentage or battery
  saving. The deterministic polling/redraw and two-extractor bounds are checked.
- **GPU:** sampled GPU subprocess private RAM overlapped at 127.9–130.7 MiB and
  125.4–130.8 MiB. Device/shared VRAM and utilization were not measured. All three
  matched 1,280 × 900 screenshots were pixel-identical; no restyling was done.
- **Storage/I/O:** snapshot payload avoidance is measured above, not claimed as
  physical disk bytes. Windows process-tree I/O observations were 96.0/74.1 MiB
  read/write before and 32.4/10.9 MiB after (medians); these include browser and
  pipe operations, not just disk. No dependencies or runtime binaries removed.
- **Network:** startup resource inventory is retained in each JSON. Search
  caching reduced controlled extractor runs from 20 to 1. Real external byte
  counts were not profiled. Earlier live YouTube search returned 12 results and
  loaded the actual player preview without creating audio files.
- **Energy/OS resources:** zero hidden polling and explicit timer teardown are
  checked, including resume. Peak processes stayed at 12; handles overlapped
  (4,781–5,027 versus 4,781–4,799). GPU, handle and thread variations did not
  justify further tuning. Device battery/power was not measured.
- **Startup/list rendering:** both remain within scoped budgets. Startup import
  profiling attributed the largest cost to yt-dlp, needed for searches/downloads.
  No lazy-loading rewrite or additional list renderer was justified.

## Cleanup and recovery checks

Pyflakes and Vulture at 100% confidence were clean after removing one unused
`json` import from `tests/check_source_search.py`. Lower-confidence HTTP callbacks
were retained because the server invokes them by protocol. Public CLI/package
entrypoints and rare error paths were retained. No package/config surface removed.
Instrumented pytest plus real app/metadata/update checks reached 70% Python line
coverage; missing lines were not treated as deletion evidence.

The final bug check reproduced a malformed saved speed/cache startup failure,
then verified recovery (zero page errors, playback speed 1, usable library).
Config tables/values and saved track metadata now reject invalid types safely.
Config writes use same-directory temporary files, flush/fsync and atomic replace;
failure preserves the original. Tests include spaces/Unicode paths and an injected
replacement failure. No persisted schema migration was introduced.

Final executed checks: 47 pytest cases; own-tone download/app, metadata and update
scripts; playlist JavaScript; full library browser interaction suite; focused
source-search browser suite; JavaScript syntax and diff whitespace checks. All
passed. Gitleaks v8.30.1, checksum-verified portable executable, scanned all
reachable Git history with redaction and found zero leaks.

Android build/signature/packaged-asset checks are recorded with the APK receipt.
Actual phone installation/upgrade, native preview navigation/save, background
playback with this panel, Android power measurements and native-runtime source
provenance remain unresolved. A forced-kill write test, standard-user install and
historical Android migration matrix were not executed. This is not release
clearance. See [verification routes](VERIFICATION.md) and [release steps](RELEASING.md).

Raw comparison, screenshots, command logs, scanner receipt and APK identity are
retained outside the checkout at
`C:/Users/there/codex/artifacts/ytmp3-source-search/optimization/`.
