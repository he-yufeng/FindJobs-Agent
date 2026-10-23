"""Interview-answer eval: does the LLM grade an answer the way a human would?

The interview chain (interview_agent.py) grades candidate answers on a 0-5
scale, and its prompt was tuned by feel. This fixture pins a handful of
synthetic interview answers with hand-labeled scores, so a prompt edit can be
compared by numbers instead of taste. All samples are synthetic (written for
this fixture, not copied from real interviews).

Offline, only the fixture validation and the scoring math run (tests/).
The live pass needs a key and is opt-in:

    FINDJOBS_EVAL=1 python -m evals.run_interview_eval [--min-within1 0.7]

Exit code is 1 if the within-±1 rate falls below --min-within1.
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

FIXTURE = Path(__file__).with_name("interview_fixture.json")
MAX_SCORE_DISTANCE = 5  # worst possible miss on the 0-5 scale


def load_fixture(path: Path = FIXTURE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def score_case(predicted: int | None, expected: int) -> dict:
    """Score one case. A failed or missing evaluation counts as a full miss:
    no answer from the chain is a failure, not neutral."""
    err = MAX_SCORE_DISTANCE if predicted is None else abs(predicted - expected)
    return {
        "answered": predicted is not None,
        "exact": err == 0,
        "within1": err <= 1,
        "err": err,
    }


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "answered": sum(r["answered"] for r in rows) / n,
        "exact": sum(r["exact"] for r in rows) / n,
        "within1": sum(r["within1"] for r in rows) / n,
        "mae": sum(r["err"] for r in rows) / n,
    }


def run_live(fixture: list[dict]) -> tuple[list[dict], dict]:
    from findjobs.interview_agent import InterviewAgent

    agent = InterviewAgent()
    rows = []
    for case in fixture:
        evaluation = agent.evaluate_answer(
            question=case["question"],
            answer=case["answer"],
            resume_data=case.get("resume"),
            job_data=case.get("job"),
        )
        predicted = None if evaluation is None else evaluation.score
        row = {"name": case["name"], **score_case(predicted, case["expected_score"])}
        rows.append(row)
        logging.info(
            "%s: answered=%s exact=%s within1=%s err=%d",
            row["name"],
            row["answered"],
            row["exact"],
            row["within1"],
            row["err"],
        )
    return rows, aggregate(rows)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-within1", type=float, default=0.7)
    args = parser.parse_args(argv)

    if os.environ.get("FINDJOBS_EVAL") != "1":
        print(
            "skipped: set FINDJOBS_EVAL=1 (and a real key in API_key-openai.md) to run live"
        )
        return 0

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    fixture = load_fixture()
    rows, summary = run_live(fixture)
    print(json.dumps(summary, indent=2))
    if summary["within1"] < args.min_within1:
        print(f"FAIL: within1={summary['within1']:.2f} < {args.min_within1}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
