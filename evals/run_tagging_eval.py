"""Skill-tagging eval: does the LLM score a resume the way a human would?

The tagging chain (tag_rate.py) changed often and was tuned by feel. This
fixture pins a handful of synthetic resumes with hand-labeled scores, so a
prompt edit can be compared by numbers instead of taste.

Offline, only the fixture validation and the scoring math run (tests/).
The live pass needs a key and is opt-in:

    FINDJOBS_EVAL=1 python -m evals.run_tagging_eval [--min-within1 0.7]

Exit code is 1 if the macro within-±1 rate falls below --min-within1.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE = Path(__file__).with_name("tagging_fixture.json")
MAX_SCORE_DISTANCE = 4  # worst possible miss on the 1-5 scale


def load_fixture(path: Path = FIXTURE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tag_vocabulary() -> set[str]:
    """every tag in data/all_labels.csv, the library the prompts draw from."""
    import csv

    tags: set[str] = set()
    with open(ROOT / "data" / "all_labels.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for tag in (row.get("tags") or "").split("|_|"):
                tag = tag.strip()
                if tag:
                    tags.add(tag)
    return tags


def score_case(predicted: dict[str, int], expected: dict[str, int]) -> dict:
    """Score one case. A tag the model never returned counts as a full miss:
    silence on a tag is a failure, not neutral."""
    exact = within1 = 0
    total_err = 0
    for tag, want in expected.items():
        got = predicted.get(tag)
        if got is None:
            total_err += MAX_SCORE_DISTANCE
            continue
        err = abs(got - want)
        total_err += err
        exact += err == 0
        within1 += err <= 1
    n = len(expected)
    return {
        "coverage": sum(1 for t in expected if t in predicted) / n,
        "exact": exact / n,
        "within1": within1 / n,
        "mae": total_err / n,
    }


def aggregate(rows: list[dict]) -> dict:
    keys = ("coverage", "exact", "within1", "mae")
    return {k: sum(r[k] for r in rows) / len(rows) for k in keys}


def run_live(fixture: list[dict]) -> tuple[list[dict], dict]:
    from findjobs.tag_rate import (
        API_KEY_FILE,
        APIKeyManager,
        SYSTEM_PROMPT_SCORE,
        build_profile_text,
        call_llm,
        load_api_keys,
        parse_llm_response,
    )

    manager = APIKeyManager(load_api_keys(API_KEY_FILE))
    rows = []
    for case in fixture:
        tags = list(case["expected"])
        user_prompt = (
            f"{build_profile_text(case['profile_rows'])}\n\n"
            "### 任务详情\n\n"
            "请为以下【待评分标签列表】中的每个标签打分。\n"
            f"【待评分标签列表】: {', '.join(tags)}"
        )
        reply = call_llm(SYSTEM_PROMPT_SCORE, user_prompt, manager)
        predicted = dict(parse_llm_response(reply, set(tags)))
        row = {"name": case["name"], **score_case(predicted, case["expected"])}
        rows.append(row)
        logging.info(
            "%s: coverage=%.2f exact=%.2f within1=%.2f mae=%.2f",
            row["name"], row["coverage"], row["exact"], row["within1"], row["mae"],
        )
    return rows, aggregate(rows)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-within1", type=float, default=0.7)
    args = parser.parse_args(argv)

    if os.environ.get("FINDJOBS_EVAL") != "1":
        print("skipped: set FINDJOBS_EVAL=1 (and a real key in API_key-openai.md) to run live")
        return 0

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    fixture = load_fixture()
    rows, macro = run_live(fixture)
    print(f"\n{macro['coverage']:.2f} coverage | {macro['exact']:.2f} exact | "
          f"{macro['within1']:.2f} within±1 | mae {macro['mae']:.2f} over {len(rows)} cases")
    if macro["within1"] < args.min_within1:
        print(f"FAIL: within±1 {macro['within1']:.2f} < {args.min_within1}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
