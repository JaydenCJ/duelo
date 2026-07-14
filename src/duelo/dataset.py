"""Aggregate battle lists into the sufficient statistics ranking needs.

A :class:`Dataset` holds, per unordered pair of items, the number of games
and the (fractional) win count of the lexicographically smaller item — ties
count as half a win for each side, the standard arena convention. It also
answers the two questions that decide whether a Bradley-Terry fit is even
well-posed:

* **Degeneracy** — an item that won everything (or lost everything) has its
  maximum-likelihood strength at +/- infinity.
* **Connectivity** — items in different connected components of the
  comparison graph share no chain of games, so no common scale exists.

A ``prior`` of pseudo-ties can be layered on top (see :meth:`Dataset.with_prior`);
it regularizes both problems at once because every pair becomes connected
and every item gains a fractional win and loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .records import Battle


@dataclass
class PairStats:
    """Games between one unordered pair. ``wins_first`` counts wins of the
    pair's first element, ties contributing 0.5 to each side; ``ties``
    keeps the raw tie count so exact W-L-T cells can be reconstructed."""

    games: float = 0.0
    wins_first: float = 0.0
    ties: float = 0.0

    @property
    def wins_second(self) -> float:
        return self.games - self.wins_first


@dataclass
class Dataset:
    items: List[str]
    pairs: Dict[Tuple[str, str], PairStats]
    n_battles: int
    n_ties: int
    # Extra pseudo-ties per pair already folded into `pairs`.
    prior: float = 0.0
    # Decisive win / tie counts per item (integers, for reporting).
    raw_wins: Dict[str, int] = field(default_factory=dict)
    raw_losses: Dict[str, int] = field(default_factory=dict)
    raw_ties: Dict[str, int] = field(default_factory=dict)

    # -- sufficient statistics -------------------------------------------

    def games_of(self, item: str) -> float:
        return sum(s.games for pair, s in self.pairs.items() if item in pair)

    def wins_of(self, item: str) -> float:
        """Fractional wins of ``item`` (ties = 0.5), including any prior."""
        total = 0.0
        for (first, _second), stats in self.pairs.items():
            if first == item:
                total += stats.wins_first
            elif _second == item:
                total += stats.wins_second
        return total

    # -- health checks ----------------------------------------------------

    def degenerate_items(self) -> List[str]:
        """Items whose fractional win count is 0 or equal to their games."""
        out = []
        for item in self.items:
            wins = self.wins_of(item)
            games = self.games_of(item)
            if games == 0 or wins <= 0 or wins >= games:
                out.append(item)
        return out

    def components(self) -> List[List[str]]:
        """Connected components of the comparison graph, largest first."""
        parent = {item: item for item in self.items}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for (a, b), stats in self.pairs.items():
            if stats.games > 0:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb
        groups: Dict[str, List[str]] = {}
        for item in self.items:
            groups.setdefault(find(item), []).append(item)
        comps = [sorted(members) for members in groups.values()]
        comps.sort(key=lambda c: (-len(c), c[0]))
        return comps

    def is_connected(self) -> bool:
        return len(self.components()) <= 1

    # -- transforms -------------------------------------------------------

    def with_prior(self, prior: float) -> "Dataset":
        """Return a copy with ``prior`` pseudo-ties added to *every* pair.

        Each pseudo-tie adds one game and half a win per side, which pulls
        strengths toward equality, bounds the MLE away from infinity, and
        connects the comparison graph.
        """
        if prior < 0:
            raise ValueError("prior must be >= 0")
        if prior == 0:
            return self
        pairs = {
            key: PairStats(s.games, s.wins_first, s.ties) for key, s in self.pairs.items()
        }
        items = self.items
        for i, a in enumerate(items):
            for b in items[i + 1 :]:
                key = (a, b) if a < b else (b, a)
                stats = pairs.setdefault(key, PairStats())
                stats.games += prior
                stats.wins_first += prior / 2.0
                stats.ties += prior
        return Dataset(
            items=list(items),
            pairs=pairs,
            n_battles=self.n_battles,
            n_ties=self.n_ties,
            prior=self.prior + prior,
            raw_wins=dict(self.raw_wins),
            raw_losses=dict(self.raw_losses),
            raw_ties=dict(self.raw_ties),
        )


def build_dataset(battles: Sequence[Battle]) -> Dataset:
    """Aggregate a battle list into a :class:`Dataset`.

    Item order is sorted for determinism; ties add 0.5 wins per side.
    """
    pairs: Dict[Tuple[str, str], PairStats] = {}
    names = set()
    raw_wins: Dict[str, int] = {}
    raw_losses: Dict[str, int] = {}
    raw_ties: Dict[str, int] = {}
    n_ties = 0
    for battle in battles:
        names.add(battle.a)
        names.add(battle.b)
        for name in (battle.a, battle.b):
            raw_wins.setdefault(name, 0)
            raw_losses.setdefault(name, 0)
            raw_ties.setdefault(name, 0)
        first, second = sorted((battle.a, battle.b))
        stats = pairs.setdefault((first, second), PairStats())
        stats.games += 1.0
        if battle.outcome == "tie":
            stats.wins_first += 0.5
            stats.ties += 1.0
            n_ties += 1
            raw_ties[battle.a] += 1
            raw_ties[battle.b] += 1
        else:
            winner = battle.winner
            assert winner is not None
            loser = battle.b if winner == battle.a else battle.a
            if winner == first:
                stats.wins_first += 1.0
            raw_wins[winner] += 1
            raw_losses[loser] += 1
    return Dataset(
        items=sorted(names),
        pairs=pairs,
        n_battles=len(battles),
        n_ties=n_ties,
        raw_wins=raw_wins,
        raw_losses=raw_losses,
        raw_ties=raw_ties,
    )
