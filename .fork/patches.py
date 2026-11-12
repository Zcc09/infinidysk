#!/usr/bin/env python3
"""Apply this fork's patches to an infinidysk source tree.

The fork itself stays byte-identical to upstream: the image workflow checks out
infinidysk/infinidysk at ``main``, runs this script over it, then builds. There is nothing to
rebase, and a patch that no longer applies fails the build loudly instead of drifting silently.

Every patch is idempotent: re-running it over an already patched tree is a no-op.
"""
from __future__ import annotations

import pathlib
import sys

IMPORT_RS = "crates/queue/src/import.rs"
CONFIG_RS = "crates/infinidysk/src/config.rs"
SETTINGS_TSX = "ui/src/pages/settings.tsx"

PATCHES: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        IMPORT_RS,
        [
            (
                "requests-in-flight",
                "/// Requests in flight per import, across all its steps.\nconst CONCURRENCY: usize = 16;",
                "/// Requests in flight per import, across all its steps.\nconst CONCURRENCY: usize = 16;\n"
                "/// [`CONCURRENCY`], overridable per host with `INFD_IMPORT_CONCURRENCY` (1-256), so import\n"
                "/// throughput can be tuned against the provider connections already paid for. Named\n"
                "/// outside the `INFINIDYSK__*` namespace, which the settings loader rejects.\n"
                "static IMPORT_CONCURRENCY: LazyLock<usize> = LazyLock::new(|| {\n"
                '    std::env::var("INFD_IMPORT_CONCURRENCY")\n'
                "        .ok()\n"
                "        .and_then(|v| v.trim().parse::<usize>().ok())\n"
                "        .map_or(CONCURRENCY, |n| n.clamp(1, 256))\n"
                "});",
            ),
            (
                "semaphore-uses-override",
                "        requests: Semaphore::new(CONCURRENCY),\n        progress,",
                "        requests: Semaphore::new(*IMPORT_CONCURRENCY),\n        progress,",
            ),
            (
                "window-follows-override",
                "/// Futures one [`join_all`] runs at once: enough to keep every request slot busy.\nconst WINDOW: usize = 4 * CONCURRENCY;",
                "/// Futures one [`join_all`] runs at once: enough to keep every request slot busy.\nstatic WINDOW: LazyLock<usize> = LazyLock::new(|| 4 * *IMPORT_CONCURRENCY);",
            ),
            (
                "window-read",
                "        while set.len() < WINDOW {",
                "        while set.len() < *WINDOW {",
            ),
            (
                "window-read-test-holds",
                "        let task = gated(1000, &started, &dropped, &gate);\n        until(|| started.load(Ordering::SeqCst) >= WINDOW).await;\n        tokio::time::sleep(Duration::from_millis(50)).await;\n        assert_eq!(started.load(Ordering::SeqCst), WINDOW);",
                "        let task = gated(1000, &started, &dropped, &gate);\n        until(|| started.load(Ordering::SeqCst) >= *WINDOW).await;\n        tokio::time::sleep(Duration::from_millis(50)).await;\n        assert_eq!(started.load(Ordering::SeqCst), *WINDOW);",
            ),
            (
                "window-read-test-drops",
                "        let task = gated(1000, &started, &dropped, &gate);\n        until(|| started.load(Ordering::SeqCst) >= WINDOW).await;\n        task.abort();",
                "        let task = gated(1000, &started, &dropped, &gate);\n        until(|| started.load(Ordering::SeqCst) >= *WINDOW).await;\n        task.abort();",
            ),
            (
                "check-can-be-skipped",
                "async fn check_articles(\n    job: &Arc<Job>,\n    outputs: Vec<Output>,\n    percent: u8,\n) -> Result<Vec<Output>, Error> {",
                "async fn check_articles(\n    job: &Arc<Job>,\n    outputs: Vec<Output>,\n    percent: u8,\n) -> Result<Vec<Output>, Error> {\n"
                "    // 0 turns the existence sample off: for callers that already know the release is\n"
                "    // sound (a health-checking indexer proxy, or triage upstream).\n"
                "    if percent == 0 {\n"
                "        return Ok(outputs);\n"
                "    }",
            ),
        ],
    ),
    (
        CONFIG_RS,
        [
            (
                "check-percent-range",
                "const CHECK_PERCENT: RangeInclusive<u8> = 5..=100;",
                "const CHECK_PERCENT: RangeInclusive<u8> = 0..=100;",
            ),
            (
                "check-percent-doc",
                "    /// Share of segments each check probes, 5 to 100; at least 5 segments.",
                "    /// Share of segments each check probes, 0 to 100; 0 skips article checking entirely.",
            ),
        ],
    ),
    (
        SETTINGS_TSX,
        [
            (
                "slider-label",
                '{draft.health.check_percent === 100 ? "Every segment" : `${draft.health.check_percent}%`}',
                '{draft.health.check_percent === 0 ? "Off" : draft.health.check_percent === 100 ? "Every segment" : `${draft.health.check_percent}%`}',
            ),
            (
                "slider-hint",
                'hint="Applies to imports and subsequent health checks. At 100%, every article is checked for availability; the entire file is not downloaded and verified."',
                'hint="Applies to imports and subsequent health checks. At 100%, every article is checked for availability; the entire file is not downloaded and verified. Off skips the check: only use it when something upstream already vets the release."',
            ),
            (
                "slider-min",
                "                      min={5}\n                      max={100}",
                "                      min={0}\n                      max={100}",
            ),
        ],
    ),
]


def patch_file(root: pathlib.Path, rel: str, pairs: list[tuple[str, str, str]]) -> None:
    path = root / rel
    if not path.is_file():
        raise SystemExit(f"missing file: {rel}")
    text = path.read_text(encoding="utf-8")  # universal newlines
    print(f"{rel}:")
    changed = False
    for name, old, new in pairs:
        if new in text:
            print(f"  = {name} (already applied)")
            continue
        found = text.count(old)
        if found != 1:
            raise SystemExit(
                f"{rel}: {name}: expected exactly 1 match, found {found} — upstream moved, "
                "update .fork/patches.py"
            )
        text = text.replace(old, new)
        changed = True
        print(f"  + {name}")
    if changed:
        path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(f"patching {root}")
    for rel, pairs in PATCHES:
        patch_file(root, rel, pairs)
    print("done")


if __name__ == "__main__":
    main()
