"""Offline half of the interview eval: fixture honesty and scoring math.

The live pass (evals/run_interview_eval.py with FINDJOBS_EVAL=1) is opt-in;
these tests guard what can be guarded without a key.
"""

from __future__ import annotations

from evals.run_interview_eval import (
    MAX_SCORE_DISTANCE,
    aggregate,
    load_fixture,
    main,
    score_case,
)


def test_fixture_cases_are_well_formed() -> None:
    fixture = load_fixture()
    assert len(fixture) >= 5, "the eval is meaningless with too few cases"
    names = set()
    for case in fixture:
        assert case["name"] not in names, f"duplicate case name {case['name']}"
        names.add(case["name"])
        assert case["question"].strip()
        assert case["answer"].strip()
        assert isinstance(case["expected_score"], int)
        assert 0 <= case["expected_score"] <= MAX_SCORE_DISTANCE


def test_fixture_spans_the_score_band() -> None:
    # a fixture that only covers one score proves nothing about the scale
    scores = {case["expected_score"] for case in load_fixture()}
    assert max(scores) >= 4 and min(scores) <= 1


def test_score_case_counts_a_missing_evaluation_as_full_miss() -> None:
    row = score_case(None, 3)
    assert row["answered"] is False
    assert row["err"] == MAX_SCORE_DISTANCE
    assert row["within1"] is False


def test_score_case_exact_and_within1() -> None:
    assert score_case(3, 3)["exact"] is True
    assert score_case(4, 3)["within1"] is True
    assert score_case(5, 3)["within1"] is False


def test_aggregate() -> None:
    rows = [score_case(3, 3), score_case(None, 3), score_case(4, 3), score_case(1, 3)]
    summary = aggregate(rows)
    assert summary["answered"] == 0.75
    assert summary["within1"] == 0.5
    assert 0 <= summary["mae"] <= MAX_SCORE_DISTANCE


def test_main_skips_live_without_opt_in(capsys) -> None:
    assert main([]) == 0
    assert "skipped" in capsys.readouterr().out
