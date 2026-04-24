"""Quick crawler health check.

Exercises every registered crawler in job_crawler.py by calling its real
.crawl() method, but monkey-patches _request so each crawler makes at most
two live HTTP calls. Reports which crawlers still return parseable jobs vs
which ones need updating (18 months after they were written).

Run from repo root:  python scripts/smoke_test_crawlers.py
"""
from __future__ import annotations

import logging
import pathlib
import sys
import time
import traceback
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# silence noisy crawler logging during smoke test
logging.basicConfig(level=logging.ERROR)

import job_crawler

CRAWLERS = job_crawler.CRAWLER_REGISTRY
MAX_CALLS_PER_CRAWLER = 2
PROBE_TIMEOUT = 15


def _patched_crawler(cls):
    orig_request = job_crawler.JobCrawlerBase._request
    instance = cls()
    counter = {"n": 0, "last_status": None}

    def limited_request(self, url, method="GET", **kwargs):
        if counter["n"] >= MAX_CALLS_PER_CRAWLER:
            return None  # tells paginated loops to break
        counter["n"] += 1
        kwargs.setdefault("timeout", PROBE_TIMEOUT)
        try:
            resp = orig_request(self, url, method=method, **kwargs)
            counter["last_status"] = resp.status_code if resp is not None else None
            return resp
        except Exception as e:
            counter["last_status"] = f"{type(e).__name__}: {str(e)[:40]}"
            return None

    instance._request = limited_request.__get__(instance, cls)
    return instance, counter


def run_one(name: str, cls) -> tuple[str, str]:
    try:
        inst, counter = _patched_crawler(cls)
    except Exception as e:
        return ("INIT_ERR", f"{type(e).__name__}: {e}")

    try:
        jobs = inst.crawl()
    except Exception as e:
        tb = traceback.format_exc().splitlines()[-1]
        return ("CRAWL_ERR", f"{tb[:90]}  (calls={counter['n']}, last={counter['last_status']})")

    if not jobs:
        return ("EMPTY", f"no jobs parsed (calls={counter['n']}, last HTTP={counter['last_status']})")

    sample = jobs[0]
    title = (sample.get("job_title") or "")[:40]
    loc = sample.get("location") or ""
    return ("OK", f"{len(jobs):3} jobs (calls={counter['n']}) — e.g. {title!r} @ {loc!r}")


def main() -> int:
    order = [
        # domestic
        "tencent", "alibaba", "baidu", "meituan", "jd", "netease", "kuaishou",
        "xiaomi", "bilibili", "didi", "pinduoduo", "huawei", "bytedance",
        # foreign
        "microsoft", "google", "amazon", "meta", "apple", "nvidia", "intel",
    ]
    names = [n for n in order if n in CRAWLERS] + [n for n in CRAWLERS if n not in order]

    print(f"\n{'='*80}")
    print(f"FindJobs-Agent crawler smoke test — {len(names)} crawlers")
    print(f"Each crawler capped at {MAX_CALLS_PER_CRAWLER} HTTP calls, {PROBE_TIMEOUT}s timeout")
    print(f"{'='*80}\n")

    results = []
    t0 = time.time()
    for i, name in enumerate(names, 1):
        print(f"[{i:2}/{len(names)}] {name:12} ... ", end="", flush=True)
        status, detail = run_one(name, CRAWLERS[name])
        print(f"{status:10} {detail}")
        results.append((name, status, detail))

    print(f"\n{'='*80}\nSummary  (elapsed {time.time()-t0:.1f}s)\n{'='*80}")
    buckets: dict[str, list[str]] = {}
    for name, status, _ in results:
        buckets.setdefault(status, []).append(name)
    for k in ["OK", "EMPTY", "CRAWL_ERR", "INIT_ERR"]:
        if k in buckets:
            print(f"  {k:10} {len(buckets[k]):2}  {', '.join(buckets[k])}")
    ok_n = len(buckets.get("OK", []))
    print(f"\nHealthy (returning jobs):   {ok_n}/{len(results)}")
    return 0 if ok_n > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
