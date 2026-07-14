"""Shared test helpers: battle builders and a simulated arena log.

Everything here is deterministic — simulated logs use a fixed
``random.Random`` seed, so every assertion on recovered ratings is exact
run to run.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List

import pytest

from duelo.records import Battle


def battle(a: str, b: str, outcome: str) -> Battle:
    return Battle(a=a, b=b, outcome=outcome)


def wins(a: str, b: str, n: int) -> List[Battle]:
    """``n`` decisive wins of ``a`` over ``b``."""
    return [Battle(a=a, b=b, outcome="a") for _ in range(n)]


def ties(a: str, b: str, n: int) -> List[Battle]:
    return [Battle(a=a, b=b, outcome="tie") for _ in range(n)]


def simulate_battles(
    true_beta: Dict[str, float],
    n: int,
    seed: int = 7,
    tie_rate: float = 0.0,
) -> List[Battle]:
    """Draw ``n`` battles from a Bradley-Terry model with known strengths."""
    rng = random.Random(seed)
    names = list(true_beta)
    out: List[Battle] = []
    for _ in range(n):
        a, b = rng.sample(names, 2)
        if tie_rate and rng.random() < tie_rate:
            out.append(Battle(a=a, b=b, outcome="tie"))
            continue
        p_a = 1.0 / (1.0 + math.exp(-(true_beta[a] - true_beta[b])))
        out.append(Battle(a=a, b=b, outcome="a" if rng.random() < p_a else "b"))
    return out


@pytest.fixture
def arena_log() -> List[Battle]:
    """A realistic five-model log: 500 battles, ties, known true order."""
    true_beta = {
        "alpha": 0.8,
        "bravo": 0.4,
        "charlie": 0.0,
        "delta": -0.4,
        "echo": -0.8,
    }
    return simulate_battles(true_beta, 500, seed=11, tie_rate=0.1)
