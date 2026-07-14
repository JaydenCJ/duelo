#!/usr/bin/env python3
"""Use duelo as a library instead of a CLI.

Loads the sample log, fits Bradley-Terry with bootstrap confidence
intervals, prints the leaderboard, and asks the model for a head-to-head
win probability. Run from the repository root:

    PYTHONPATH=src python3 examples/rank_from_python.py
"""

from __future__ import annotations

import os

from duelo import build_dataset, fit_bradley_terry, load_battles, rank_bradley_terry

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    battles = load_battles(os.path.join(HERE, "battles.jsonl"))

    board = rank_bradley_terry(battles, ci="bootstrap", rounds=200, seed=42)
    print(f"{board.method}: {board.n_battles} battles, {board.n_ties} ties")
    for rank, row in enumerate(board.items, start=1):
        assert row.ci_low is not None and row.ci_high is not None
        print(
            f"{rank}. {row.name:<12} {row.rating:7.1f}  "
            f"[{row.ci_low:.1f}, {row.ci_high:.1f}]  "
            f"({row.wins}W-{row.losses}L-{row.ties}T)"
        )

    fit = fit_bradley_terry(build_dataset(battles))
    top, runner_up = board.names()[0], board.names()[1]
    p = fit.win_probability(top, runner_up)
    print(f"\nP({top} beats {runner_up}) = {p:.3f}")


if __name__ == "__main__":
    main()
