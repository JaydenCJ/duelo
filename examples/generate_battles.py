#!/usr/bin/env python3
"""Regenerate the sample battle log shipped in this directory.

Simulates 400 pairwise comparisons between five fictional models with known
Bradley-Terry strengths (so you can check that duelo recovers the true
order), plus an 8% tie rate. Fully deterministic: same seed, same file.

Usage:
    python3 examples/generate_battles.py [out.jsonl]
"""

from __future__ import annotations

import json
import math
import random
import sys

SEED = 7
N_BATTLES = 400
TIE_RATE = 0.08

# True log-strengths. Expected finishing order is exactly this list.
TRUE_BETA = {
    "nova-large": 0.9,
    "crest-2": 0.5,
    "puffin-xl": 0.1,
    "nova-mini": -0.4,
    "harbor-1": -1.1,
}


def simulate(seed: int = SEED, n: int = N_BATTLES):
    rng = random.Random(seed)
    names = list(TRUE_BETA)
    battles = []
    for _ in range(n):
        a, b = rng.sample(names, 2)
        if rng.random() < TIE_RATE:
            winner = "tie"
        else:
            p_a = 1.0 / (1.0 + math.exp(-(TRUE_BETA[a] - TRUE_BETA[b])))
            winner = "a" if rng.random() < p_a else "b"
        battles.append({"a": a, "b": b, "winner": winner})
    return battles


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "examples/battles.jsonl"
    battles = simulate()
    with open(out, "w", encoding="utf-8") as fh:
        for row in battles:
            fh.write(json.dumps(row) + "\n")
    print(f"wrote {len(battles)} battles to {out}")


if __name__ == "__main__":
    main()
