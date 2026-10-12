"""Liveness check for the job_crawler_v2 registry.

Runs every registered v2 crawler against its real endpoint, monkey-patching
_request so each crawler makes at most three live HTTP calls. Reports which
adapters still return parseable jobs and which have gone stale, so the
registry only ever claims companies that actually work. Selenium adapters
are skipped unless --with-selenium is passed (they need a local Chrome).

Run from repo root:  python scripts/verify_crawlers_v2.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.ERROR)

import findjobs.job_crawler_v2 as v2

CRAWLERS = v2.CRAWLERS
NAMES = v2.NAMES
MAX_CALLS_PER_CRAWLER = 3
PROBE_TIMEOUT = 15


def _is_selenium(cls) -> bool:
    return isinstance(cls, type) and issubclass(cls, v2.SeleniumCrawlerBase)


def run_one(name: str, cls) -> tuple[str, str]:
    try:
        inst = cls(max_jobs=3)
    except Exception as e:
        return ("INIT_ERR", f"{type(e).__name__}: {e}")

    counter = {"n": 0, "last": None}
    orig_request = v2.JobCrawlerBase._request

    def limited_request(self, url, method="GET", **kwargs):
        if counter["n"] >= MAX_CALLS_PER_CRAWLER:
            return None  # tells paginated loops to stop
        counter["n"] += 1
        kwargs["timeout"] = PROBE_TIMEOUT
        try:
            resp = orig_request(self, url, method=method, **kwargs)
            counter["last"] = resp.status_code if resp is not None else None
            return resp
        except Exception as e:  # orig swallows most of these itself
            counter["last"] = f"{type(e).__name__}: {str(e)[:40]}"
            return None

    inst._request = limited_request.__get__(inst, cls)

    t0 = time.time()
    try:
        jobs = inst.crawl()
    except Exception:
        tb = traceback.format_exc().splitlines()[-1]
        return ("CRAWL_ERR", f"{tb[:90]}  (calls={counter['n']}, last={counter['last']})")
    elapsed = time.time() - t0

    if not jobs:
        return ("EMPTY", f"no jobs parsed (calls={counter['n']}, last HTTP={counter['last']}, {elapsed:.0f}s)")

    sample = jobs[0]
    title = (sample.get("job_title") or "")[:40]
    loc = sample.get("location") or ""
    url = sample.get("apply_url") or ""
    sane = bool(title) and bool(url)
    tag = "OK" if sane else "THIN"
    return (tag, f"{len(jobs):3} jobs (calls={counter['n']}, {elapsed:.0f}s) - e.g. {title!r} @ {loc!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-selenium", action="store_true", help="also probe Selenium adapters (needs Chrome)")
    ap.add_argument("--only", nargs="*", default=None, help="probe only these registry keys")
    ap.add_argument("--json", default=None, help="write results to this JSON file")
    args = ap.parse_args()

    names = args.only or list(CRAWLERS)
    skipped = []

    print(f"\n{'=' * 80}")
    print(f"job_crawler_v2 liveness check - {len(names)} adapters")
    print(f"Capped at {MAX_CALLS_PER_CRAWLER} HTTP calls each, {PROBE_TIMEOUT}s timeout")
    print(f"{'=' * 80}\n")

    results = []
    t0 = time.time()
    for i, name in enumerate(names, 1):
        cls = CRAWLERS[name]
        if _is_selenium(cls) and not args.with_selenium:
            skipped.append(name)
            continue
        print(f"[{i:2}/{len(names)}] {name:12} ... ", end="", flush=True)
        status, detail = run_one(name, cls)
        print(f"{status:10} {detail}")
        results.append((name, status, detail))

    if skipped:
        print(f"\nskipped (Selenium, rerun with --with-selenium): {', '.join(skipped)}")

    print(f"\n{'=' * 80}\nSummary  (elapsed {time.time() - t0:.1f}s)\n{'=' * 80}")
    buckets: dict[str, list[str]] = {}
    for name, status, _ in results:
        buckets.setdefault(status, []).append(name)
    for k in ["OK", "THIN", "EMPTY", "CRAWL_ERR", "INIT_ERR"]:
        if k in buckets:
            print(f"  {k:10} {len(buckets[k]):2}  {', '.join(buckets[k])}")
    ok_n = len(buckets.get("OK", [])) + len(buckets.get("THIN", []))
    print(f"\nLive (returning jobs): {ok_n}/{len(results)}")

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(
                [{"name": n, "status": s, "detail": d} for n, s, d in results],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if ok_n > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
