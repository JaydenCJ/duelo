"""Rendering: every format shows the same numbers, escapes correctly, and
the matrix/stats views reconstruct exact integer counts."""

from __future__ import annotations

import csv
import io
import json

import pytest

from duelo.dataset import build_dataset
from duelo.ranking import rank_bradley_terry
from duelo.report import render_leaderboard, render_matrix, render_stats
from conftest import ties, wins


@pytest.fixture
def board(arena_log):
    return rank_bradley_terry(arena_log, ci="analytic")


def test_table_has_title_header_and_ranked_rows(board):
    text = render_leaderboard(board, "table")
    lines = text.splitlines()
    assert "bradley-terry leaderboard" in lines[0]
    assert lines[1].startswith("rank")
    assert "95% CI" in lines[1]
    assert lines[3].lstrip().startswith("1  alpha")


def test_markdown_is_a_valid_pipe_table(board):
    text = render_leaderboard(board, "markdown")
    lines = text.splitlines()
    assert lines[0].startswith("| rank |")
    assert set(lines[1].replace("|", "").replace(" ", "")) <= {"-", ":"}
    assert len(lines) == 2 + len(board.items)


def test_markdown_escapes_pipes_in_item_names():
    battles = wins("weird|name", "plain", 2) + wins("plain", "weird|name", 1)
    board = rank_bradley_terry(battles, ci="none")
    text = render_leaderboard(board, "markdown")
    assert "weird\\|name" in text


def test_json_output_is_machine_readable_and_ranked(board):
    payload = json.loads(render_leaderboard(board, "json"))
    assert payload["method"] == "bradley-terry"
    assert payload["ci"] == {"method": "analytic", "level": 0.95}
    ranks = [item["rank"] for item in payload["items"]]
    assert ranks == list(range(1, len(payload["items"]) + 1))
    first = payload["items"][0]
    assert first["ci_low"] < first["rating"] < first["ci_high"]


def test_csv_round_trips_and_unknown_format_raises(board):
    rows = list(csv.reader(io.StringIO(render_leaderboard(board, "csv"))))
    assert rows[0][0] == "rank"
    assert len(rows) == 1 + len(board.items)
    assert rows[1][1] == "alpha"
    with pytest.raises(ValueError, match="unknown output format"):
        render_leaderboard(board, "yaml")


def test_matrix_cells_reconstruct_exact_w_l_t():
    battles = wins("a", "b", 3) + wins("b", "a", 1) + ties("a", "b", 2)
    text = render_matrix(build_dataset(battles), "table")
    assert "3-1-2" in text  # a's row vs b
    assert "1-3-2" in text  # b's row vs a
    sparse = render_matrix(build_dataset(wins("a", "b", 1) + wins("b", "c", 1)), "table")
    row_a = next(line for line in sparse.splitlines() if line.startswith("a "))
    assert row_a.split()[1] == "-"  # a vs a: diagonal
    assert row_a.split()[3] == "."  # a vs c: never played


def test_matrix_json_lists_each_unordered_pair_once():
    battles = wins("a", "b", 2) + ties("b", "c", 1)
    payload = json.loads(render_matrix(build_dataset(battles), "json"))
    pairs = {(cell["a"], cell["b"]) for cell in payload["cells"]}
    assert pairs == {("a", "b"), ("b", "c")}


def test_stats_flags_disconnection_and_degeneracy():
    battles = wins("a1", "a2", 2) + wins("b1", "b2", 2)
    text = render_stats(build_dataset(battles), "table")
    assert "DISCONNECTED" in text
    assert "degenerate:  a1, a2, b1, b2" in text


def test_stats_healthy_log_reports_none_degenerate(arena_log):
    text = render_stats(build_dataset(arena_log), "table")
    assert "degenerate:  none" in text
    assert "components:  1" in text
    assert "pair coverage: 10/10 observed" in text


def test_stats_csv_is_the_per_item_table(arena_log):
    # CSV carries the per-item rows; the fit-health summary lives in JSON.
    rows = list(csv.reader(io.StringIO(render_stats(build_dataset(arena_log), "csv"))))
    assert rows[0] == ["item", "games", "wins", "losses", "ties"]
    assert len(rows) == 1 + 5
    with pytest.raises(ValueError, match="unknown output format"):
        render_stats(build_dataset(arena_log), "yaml")


def test_stats_json_per_item_counts(arena_log):
    payload = json.loads(render_stats(build_dataset(arena_log), "json"))
    assert payload["battles"] == 500
    per_item = {row["name"]: row for row in payload["per_item"]}
    assert set(per_item) == {"alpha", "bravo", "charlie", "delta", "echo"}
    total_games = sum(row["games"] for row in per_item.values())
    assert total_games == 2 * payload["battles"]
