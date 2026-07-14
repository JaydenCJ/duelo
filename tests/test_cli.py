"""End-to-end CLI tests: real files in, rendered leaderboards out, correct
exit codes on every failure path a user can hit."""

from __future__ import annotations

import json

import pytest

from duelo import __version__
from duelo.cli import main


@pytest.fixture
def log_file(tmp_path):
    path = tmp_path / "battles.jsonl"
    rows = (
        ['{"a": "north", "b": "south", "winner": "a"}'] * 6
        + ['{"a": "south", "b": "north", "winner": "a"}'] * 3
        + ['{"a": "north", "b": "south", "winner": "tie"}'] * 2
        + ['{"a": "south", "b": "east", "winner": "a"}'] * 5
        + ['{"a": "east", "b": "south", "winner": "a"}'] * 4
        + ['{"a": "east", "b": "north", "winner": "b"}'] * 4
        + ['{"a": "north", "b": "east", "winner": "b"}'] * 2
    )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(path)


def test_rank_prints_a_leaderboard(log_file, capsys):
    assert main(["rank", log_file]) == 0
    out = capsys.readouterr().out
    assert "bradley-terry leaderboard" in out
    assert "north" in out and "95% CI" in out


def test_rank_json_output_parses_and_orders(log_file, capsys):
    assert main(["rank", log_file, "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    names = [item["name"] for item in payload["items"]]
    assert names[0] == "north"  # strongest record in the fixture
    assert payload["items"][0]["ci_low"] is not None


def test_rank_bootstrap_is_reproducible(log_file, capsys):
    assert main(["rank", log_file, "--ci", "bootstrap", "--rounds", "50", "--seed", "9"]) == 0
    first = capsys.readouterr().out
    assert main(["rank", log_file, "--ci", "bootstrap", "--rounds", "50", "--seed", "9"]) == 0
    assert capsys.readouterr().out == first


def test_elo_command_with_custom_k(log_file, capsys):
    assert main(["elo", log_file, "--k", "24", "--ci", "none"]) == 0
    out = capsys.readouterr().out
    assert "elo leaderboard" in out


def test_matrix_command(log_file, capsys):
    assert main(["matrix", log_file]) == 0
    out = capsys.readouterr().out
    assert "head-to-head" in out
    assert "6-3-2" in out  # north vs south from the fixture


def test_stats_command(log_file, capsys):
    assert main(["stats", log_file]) == 0
    out = capsys.readouterr().out
    assert "battles:     26" in out
    assert "degenerate:  none" in out


def test_degenerate_log_exits_1_with_prior_hint(tmp_path, capsys):
    path = tmp_path / "shutout.jsonl"
    path.write_text('{"a": "x", "b": "y", "winner": "a"}\n' * 3, encoding="utf-8")
    assert main(["rank", str(path)]) == 1
    err = capsys.readouterr().err
    assert "duelo: error:" in err
    assert "--prior" in err


def test_prior_flag_repairs_the_same_log(tmp_path, capsys):
    path = tmp_path / "shutout.jsonl"
    path.write_text('{"a": "x", "b": "y", "winner": "a"}\n' * 3, encoding="utf-8")
    assert main(["rank", str(path), "--prior", "0.5"]) == 0
    assert "x" in capsys.readouterr().out


def test_parse_error_exits_1_with_location(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"a": "x", "b": "y", "winner": "a"}\n{broken\n', encoding="utf-8")
    assert main(["rank", str(path)]) == 1
    assert "bad.jsonl:2" in capsys.readouterr().err


def test_csv_input_with_custom_columns(tmp_path, capsys):
    path = tmp_path / "prefs.csv"
    path.write_text(
        "champ,challenger,verdict\nx,y,champ\nx,y,challenger\nx,y,tie\n", encoding="utf-8"
    )
    code = main(
        [
            "stats",
            str(path),
            "--col-a",
            "champ",
            "--col-b",
            "challenger",
            "--col-winner",
            "verdict",
        ]
    )
    assert code == 0
    assert "battles:     3" in capsys.readouterr().out


def test_stdin_input(log_file, capsys, monkeypatch):
    import io

    with open(log_file, "r", encoding="utf-8") as fh:
        content = fh.read()
    monkeypatch.setattr("sys.stdin", io.StringIO(content))
    assert main(["stats", "-"]) == 0
    assert "battles:     26" in capsys.readouterr().out


def test_version_flag_and_bare_invocation(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"duelo {__version__}"
    assert main([]) == 2  # no command: print help, exit 2
    assert "rank" in capsys.readouterr().out


def test_base_and_scale_flags_move_the_display_scale(log_file, capsys):
    assert main(["rank", log_file, "--base", "1500", "--ci", "none", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    mean = sum(item["rating"] for item in payload["items"]) / len(payload["items"])
    # Centered log-strengths average zero, so mean display rating == base.
    assert abs(mean - 1500.0) < 0.01
