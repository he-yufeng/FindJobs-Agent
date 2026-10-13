"""Offline half of the tagging eval: fixture honesty and scoring math.

The live pass (evals/run_tagging_eval.py with FINDJOBS_EVAL=1) is opt-in;
these tests guard what can be guarded without a key.
"""

from __future__ import annotations

from evals.run_tagging_eval import (
    MAX_SCORE_DISTANCE,
    aggregate,
    load_fixture,
    load_tag_vocabulary,
    main,
    score_case,
)


def test_fixture_tags_all_exist_in_the_label_library() -> None:
    vocab = load_tag_vocabulary()
    assert len(vocab) > 1000  # sanity: the library really loaded
    for case in load_fixture():
        for tag in case["expected"]:
            assert tag in vocab, f"{case['name']}: '{tag}' is not in all_labels.csv"


def test_fixture_shape_is_sane() -> None:
    fixture = load_fixture()
    assert len(fixture) >= 5  # fewer cases than this and the metric is noise
    names = [c["name"] for c in fixture]
    assert len(names) == len(set(names))
    for case in fixture:
        assert case["profile_rows"], case["name"]
        assert len(case["expected"]) >= 5, case["name"]
        for tag, score in case["expected"].items():
            assert isinstance(tag, str) and tag.strip()
            assert 1 <= score <= 5


def test_score_case_math() -> None:
    expected = {"A": 5, "B": 3, "C": 1, "D": 4}
    predicted = {"A": 5, "B": 4, "C": 3, "D": 4}
    row = score_case(predicted, expected)
    assert row["coverage"] == 1.0
    assert row["exact"] == 0.5  # A and D
    # C is off by 2, the rest within 1
    assert row["within1"] == 0.75
    assert row["mae"] == (0 + 1 + 2 + 0) / 4


def test_score_case_missing_prediction_counts_as_full_miss() -> None:
    expected = {"A": 3, "B": 3}
    row = score_case({"A": 3}, expected)
    assert row["coverage"] == 0.5
    assert row["exact"] == 0.5
    assert row["within1"] == 0.5
    assert row["mae"] == MAX_SCORE_DISTANCE / 2


def test_aggregate_is_macro_average() -> None:
    rows = [
        {"coverage": 1.0, "exact": 1.0, "within1": 1.0, "mae": 0.0},
        {"coverage": 0.5, "exact": 0.0, "within1": 0.5, "mae": 2.0},
    ]
    macro = aggregate(rows)
    assert macro["within1"] == 0.75
    assert macro["mae"] == 1.0


def test_runner_skips_cleanly_without_the_opt_in(monkeypatch, capsys) -> None:
    monkeypatch.delenv("FINDJOBS_EVAL", raising=False)
    assert main([]) == 0
    assert "skipped" in capsys.readouterr().out
