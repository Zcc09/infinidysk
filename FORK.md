# infinidysk fork (Zcc09)

A **patch-only** fork of [infinidysk/infinidysk](https://github.com/infinidysk/infinidysk) (MIT).
No upstream file is modified here. `.fork/patches.py` is applied at build time over a fresh
checkout of upstream `main`, so this fork tracks upstream automatically and cannot drift into a
merge conflict.

## What the patches do

1. **Import concurrency is tunable** (`crates/queue/src/import.rs`). The compiled default stays at
   16 requests in flight per import; `INFINIDYSK__QUEUE__IMPORT_CONCURRENCY` overrides it per host
   (clamped 1-256) and the `join_all` window scales with it.
2. **Article checking can be turned off** (`crates/queue/src/import.rs`, `crates/infinidysk/src/config.rs`).
   `health.check_percent` accepts `0`, which skips `check_articles()` entirely instead of failing
   validation. It was 5-100.
3. **The UI reaches it** (`ui/src/pages/settings.tsx`). The sample-size slider starts at 0 and reads
   "Off".

## Why

`check_articles()` STATs a sample of a release's segments over NNTP, `CONCURRENCY` at a time. On a
43 GB remux that measured ~1,070 round-trips and ~67 s of pure latency before the file could be
served, with `fetch_bps` at 0 and nothing written to disk. Both the sample rate and the in-flight
cap were compiled in, with no runtime knob.

## Images

`ghcr.io/zcc09/infinidysk-next:fork` — rebuilt daily from upstream `main` (skipped when that commit
is already built), or on demand through the Actions UI / `workflow_dispatch`.
