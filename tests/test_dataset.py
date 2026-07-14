"""Aggregation into sufficient statistics: tie halving, degeneracy and
connectivity detection, and prior pseudo-ties."""

from __future__ import annotations

import pytest

from duelo.dataset import build_dataset
from conftest import ties, wins


def test_items_are_sorted_for_determinism():
    data = build_dataset(wins("zeta", "alpha", 1) + wins("mid", "alpha", 1))
    assert data.items == ["alpha", "mid", "zeta"]


def test_pair_stats_orient_to_lexicographically_first_item():
    data = build_dataset(wins("b", "a", 3) + wins("a", "b", 1))
    stats = data.pairs[("a", "b")]
    assert stats.games == 4
    assert stats.wins_first == 1  # "a" won once
    assert stats.wins_second == 3


def test_ties_count_half_a_win_but_raw_counts_stay_integer():
    data = build_dataset(wins("a", "b", 3) + ties("a", "b", 1) + wins("b", "a", 2))
    assert data.wins_of("a") == 3.5
    assert data.wins_of("b") == 2.5
    assert data.n_ties == 1
    assert data.pairs[("a", "b")].ties == 1
    assert data.raw_wins["a"] == 3
    assert data.raw_losses["a"] == 2
    assert data.raw_ties["a"] == 1


def test_degenerate_items_flags_shutouts_both_directions():
    data = build_dataset(wins("champ", "chump", 5))
    assert data.degenerate_items() == ["champ", "chump"]


def test_one_tie_removes_degeneracy():
    data = build_dataset(wins("champ", "chump", 5) + ties("champ", "chump", 1))
    assert data.degenerate_items() == []


def test_components_detects_disconnected_leagues_and_chains():
    data = build_dataset(
        wins("a1", "a2", 1) + wins("a2", "a1", 1) + wins("b1", "b2", 1) + wins("b2", "b1", 1)
    )
    assert not data.is_connected()
    assert data.components() == [["a1", "a2"], ["b1", "b2"]]
    chained = build_dataset(
        wins("a", "b", 1) + wins("b", "a", 1) + wins("b", "c", 1) + wins("c", "b", 1)
    )
    assert chained.is_connected()


def test_with_prior_adds_pseudo_ties_to_every_pair():
    data = build_dataset(wins("a", "b", 1) + wins("b", "a", 1) + wins("c", "a", 1) + wins("a", "c", 1))
    primed = data.with_prior(0.5)
    # Pair (b, c) had no games; the prior creates it and connects nothing new
    # here, but bounds all strengths.
    assert primed.pairs[("b", "c")].games == 0.5
    assert primed.pairs[("b", "c")].wins_first == 0.25
    assert primed.prior == 0.5
    # Original dataset is untouched; prior 0 is the identity, negatives rejected.
    assert ("b", "c") not in data.pairs
    assert data.with_prior(0.0) is data
    with pytest.raises(ValueError, match=">= 0"):
        data.with_prior(-1.0)


def test_with_prior_connects_a_disconnected_graph():
    data = build_dataset(wins("a", "b", 1) + wins("b", "a", 1) + ties("c", "d", 2))
    assert not data.is_connected()
    assert data.with_prior(0.1).is_connected()


def test_wins_and_games_of_unseen_pairing(arena_log):
    data = build_dataset(arena_log)
    total_games = sum(data.games_of(item) for item in data.items)
    assert total_games == 2 * data.n_battles  # each battle counts for both sides
    total_wins = sum(data.wins_of(item) for item in data.items)
    assert total_wins == pytest.approx(data.n_battles)
