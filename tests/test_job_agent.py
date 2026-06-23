from job_agent import (
    deduplicate,
    format_skill_string,
    normalize_text,
    parse_llm_response,
)

_VALID = {"Python", "Machine Learning", "Data Analysis", "SQL"}


def test_parse_keeps_multi_word_tags():
    # A multi-word skill like "Machine Learning" must be captured whole, not
    # truncated to its last word (which wouldn't be in the tag set).
    parsed = parse_llm_response(
        "Python:5\nMachine Learning:4\nData Analysis:3", _VALID
    )
    assert parsed == [("Python", 5), ("Machine Learning", 4), ("Data Analysis", 3)]


def test_parse_handles_multiple_tags_on_one_line():
    parsed = parse_llm_response("Python:5 Machine Learning:4", _VALID)
    assert parsed == [("Python", 5), ("Machine Learning", 4)]


def test_parse_accepts_fullwidth_colon():
    parsed = parse_llm_response("SQL：2", _VALID)
    assert parsed == [("SQL", 2)]


def test_parse_drops_unknown_and_out_of_range():
    # Unknown tags and scores outside 1-5 are ignored.
    parsed = parse_llm_response("Unknown:5\nPython:9\nPython:4", _VALID)
    assert parsed == [("Python", 4)]


def test_parse_dedupes_keeping_first():
    parsed = parse_llm_response("Python:5\nPython:2", _VALID)
    assert parsed == [("Python", 5)]


def test_parse_strips_markdown_emphasis():
    parsed = parse_llm_response("**Python**:5", _VALID)
    assert parsed == [("Python", 5)]


def test_parse_empty_returns_empty():
    assert parse_llm_response("", _VALID) == []


def test_normalize_text_strips_whitespace_and_lowercases():
    assert normalize_text("  Hello   World  ") == "helloworld"
    assert normalize_text(None) == ""
    assert normalize_text(123) == "123"


def test_deduplicate_preserves_order_and_skips_empty():
    assert deduplicate(["a", "b", "a", "", "c", "b"]) == ["a", "b", "c"]


def test_format_skill_string_matches_csv_shape():
    assert format_skill_string([("Python", 5), ("SQL", 3)]) == "Python , 5 , AI | SQL , 3 , AI"
