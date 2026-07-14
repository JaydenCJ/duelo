"""Parsing battle logs: JSONL, CSV, key aliases, winner normalization, and
the error messages users actually see when a log line is malformed."""

from __future__ import annotations

import pytest

from duelo.errors import ParseError
from duelo.records import (
    Battle,
    load_battles,
    normalize_winner,
    parse_csv,
    parse_jsonl,
    sniff_format,
)


def test_jsonl_basic_and_model_a_b_aliases():
    battles = parse_jsonl(['{"a": "x", "b": "y", "winner": "a"}'])
    assert battles == [Battle("x", "y", "a")]
    aliased = parse_jsonl(['{"model_a": "x", "model_b": "y", "winner": "model_b"}'])
    assert aliased[0].outcome == "b"
    assert aliased[0].winner == "y"


def test_jsonl_skips_blank_and_comment_lines():
    lines = ["", "# generated 2026-07-01", '{"a": "x", "b": "y", "winner": "tie"}', "  "]
    assert len(parse_jsonl(lines)) == 1


def test_jsonl_invalid_json_reports_line_number():
    with pytest.raises(ParseError, match=r"battles\.jsonl:2"):
        parse_jsonl(['{"a": "x", "b": "y", "winner": "a"}', "{oops"], source="battles.jsonl")


def test_jsonl_bad_rows_are_errors_not_silent_skips():
    # Silently dropping rows would bias the ranking; both must be loud.
    with pytest.raises(ParseError, match="unrecognized winner value 'c'"):
        parse_jsonl(['{"a": "x", "b": "y", "winner": "c"}'])
    with pytest.raises(ParseError, match="winner"):
        parse_jsonl(['{"a": "x", "b": "y"}'])


def test_jsonl_explicit_custom_keys():
    battles = parse_jsonl(
        ['{"champ": "x", "challenger": "y", "verdict": "challenger"}'],
        a_key="champ",
        b_key="challenger",
        winner_key="verdict",
    )
    assert battles[0].outcome == "b"


def test_winner_accepts_item_name_and_tie_variants():
    assert normalize_winner("gpt-x", "gpt-x", "other") == "a"
    assert normalize_winner("other", "gpt-x", "other") == "b"
    assert normalize_winner("tie (bothbad)", "x", "y") == "tie"
    assert normalize_winner("DRAW", "x", "y") == "tie"
    assert normalize_winner("Model_A", "x", "y") == "a"


def test_winner_item_name_beats_side_label_when_items_are_named_a_b():
    # An item literally called "b" must win as the item, not the side label.
    assert normalize_winner("b", "b", "z") == "a"  # "b" IS item a here


def test_battle_rejects_self_play_and_empty_names():
    with pytest.raises(ValueError, match="itself"):
        Battle("x", "x", "a")
    with pytest.raises(ValueError, match="non-empty"):
        Battle("", "y", "a")


def test_csv_with_header_extra_columns_and_blank_trailing_line():
    text = "timestamp,model_a,model_b,winner\n2026-07-01,x,y,tie\n2026-07-02,x,y,model_a\n\n"
    battles = parse_csv(text)
    assert [b.outcome for b in battles] == ["tie", "a"]


def test_csv_empty_file_is_a_parse_error():
    with pytest.raises(ParseError, match="no header"):
        parse_csv("")


def test_load_battles_sniffs_format_and_roundtrips_jsonl_and_csv(tmp_path):
    assert sniff_format("log.csv", "") == "csv"
    assert sniff_format("log.txt", '{"a": 1}') == "jsonl"
    assert sniff_format("log.txt", "a,b,winner") == "csv"
    jsonl = tmp_path / "battles.jsonl"
    jsonl.write_text('{"a": "x", "b": "y", "winner": "b"}\n', encoding="utf-8")
    csv_file = tmp_path / "battles.csv"
    csv_file.write_text("a,b,winner\nx,y,b\n", encoding="utf-8")
    assert load_battles(str(jsonl)) == load_battles(str(csv_file))


def test_load_battles_missing_file_is_a_duelo_error(tmp_path):
    with pytest.raises(ParseError, match="cannot read file"):
        load_battles(str(tmp_path / "nope.jsonl"))
