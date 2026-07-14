"""The ``duelo`` command line.

Subcommands:

* ``rank``   — Bradley-Terry leaderboard with confidence intervals.
* ``elo``    — sequential Elo leaderboard (bootstrap CIs).
* ``matrix`` — head-to-head win/loss/tie matrix.
* ``stats``  — dataset summary: volume, coverage, connectivity, degeneracy.

All subcommands read the same log formats (JSON Lines or CSV, ``-`` for
stdin) and share ``--format`` for table/markdown/json/csv output. Errors
print one actionable line to stderr and exit 1; argparse usage errors keep
argparse's exit 2.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, Sequence

from . import __version__, bootstrap, ranking, report
from .dataset import build_dataset
from .errors import DueloError
from .records import load_battles


def _add_input_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("log", help="battle log file (JSONL or CSV), or '-' for stdin")
    parser.add_argument(
        "--input-format",
        choices=("auto", "jsonl", "csv"),
        default="auto",
        help="input format (default: auto-detect from extension/content)",
    )
    parser.add_argument("--col-a", default=None, help="column/key holding the first item")
    parser.add_argument("--col-b", default=None, help="column/key holding the second item")
    parser.add_argument(
        "--col-winner", default=None, help="column/key holding the winner/outcome"
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=report.FORMATS,
        default="table",
        help="output format (default: table)",
    )


def _add_ci_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--level",
        type=float,
        default=0.95,
        help="confidence level in (0, 1) (default: 0.95)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=bootstrap.DEFAULT_ROUNDS,
        help=f"bootstrap resamples (default: {bootstrap.DEFAULT_ROUNDS})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=bootstrap.DEFAULT_SEED,
        help=f"bootstrap RNG seed for reproducible CIs (default: {bootstrap.DEFAULT_SEED})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duelo",
        description=(
            "Bradley-Terry and Elo rankings with confidence intervals "
            "from pairwise preference logs."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"duelo {__version__}"
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    rank = sub.add_parser(
        "rank",
        help="Bradley-Terry leaderboard with confidence intervals",
        description=(
            "Fit the Bradley-Terry model on the whole log (order-independent) "
            "and report ratings on an Elo-like scale with confidence intervals."
        ),
    )
    _add_input_options(rank)
    rank.add_argument(
        "--ci",
        choices=(ranking.CI_ANALYTIC, ranking.CI_BOOTSTRAP, ranking.CI_NONE),
        default=ranking.CI_ANALYTIC,
        help="confidence interval method (default: analytic)",
    )
    _add_ci_options(rank)
    rank.add_argument(
        "--prior",
        type=float,
        default=0.0,
        help="pseudo-ties added to every pair; regularizes shutouts and "
        "disconnected graphs (default: 0)",
    )
    rank.add_argument(
        "--base",
        type=float,
        default=ranking.DEFAULT_BASE,
        help="display-scale anchor rating (default: 1000)",
    )
    rank.add_argument(
        "--scale",
        type=float,
        default=ranking.DEFAULT_SCALE,
        help="display-scale points per 10x strength (default: 400, Elo-like)",
    )

    elo = sub.add_parser(
        "elo",
        help="sequential Elo leaderboard (order-dependent)",
        description=(
            "Replay the log in order with standard Elo updates. Prefer 'rank' "
            "for a static log; use 'elo' when recency should matter."
        ),
    )
    _add_input_options(elo)
    elo.add_argument(
        "--ci",
        choices=(ranking.CI_BOOTSTRAP, ranking.CI_NONE),
        default=ranking.CI_BOOTSTRAP,
        help="confidence interval method (default: bootstrap)",
    )
    _add_ci_options(elo)
    elo.add_argument("--k", type=float, default=32.0, help="K-factor (default: 32)")
    elo.add_argument(
        "--initial", type=float, default=1000.0, help="starting rating (default: 1000)"
    )
    elo.add_argument(
        "--scale",
        type=float,
        default=400.0,
        help="Elo curve scale (default: 400)",
    )

    matrix = sub.add_parser(
        "matrix",
        help="head-to-head win/loss/tie matrix",
        description="Print the pairwise W-L-T matrix (row's perspective).",
    )
    _add_input_options(matrix)

    stats = sub.add_parser(
        "stats",
        help="dataset summary: volume, coverage, connectivity, degeneracy",
        description=(
            "Summarize the log and flag anything that would make a "
            "Bradley-Terry fit ill-posed."
        ),
    )
    _add_input_options(stats)

    return parser


def _load(args: argparse.Namespace):
    return load_battles(
        args.log,
        fmt=args.input_format,
        a_key=args.col_a,
        b_key=args.col_b,
        winner_key=args.col_winner,
    )


def _run(args: argparse.Namespace) -> str:
    battles = _load(args)
    if args.command == "rank":
        result = ranking.rank_bradley_terry(
            battles,
            prior=args.prior,
            base=args.base,
            scale=args.scale,
            ci=args.ci,
            level=args.level,
            rounds=args.rounds,
            seed=args.seed,
        )
        return report.render_leaderboard(result, args.format)
    if args.command == "elo":
        result = ranking.rank_elo(
            battles,
            k=args.k,
            initial=args.initial,
            scale=args.scale,
            ci=args.ci,
            level=args.level,
            rounds=args.rounds,
            seed=args.seed,
        )
        return report.render_leaderboard(result, args.format)
    if args.command == "matrix":
        return report.render_matrix(build_dataset(battles), args.format)
    if args.command == "stats":
        return report.render_stats(build_dataset(battles), args.format)
    raise AssertionError(f"unhandled command {args.command!r}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns the process exit code instead of calling exit."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        output = _run(args)
    except DueloError as exc:
        print(f"duelo: error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"duelo: error: {exc}", file=sys.stderr)
        return 1
    try:
        print(output)
        sys.stdout.flush()
    except BrokenPipeError:
        # Downstream (e.g. `| head`) closed the pipe; exit quietly. Point
        # stdout at devnull so interpreter shutdown does not complain.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    return 0


def console_main() -> None:  # pragma: no cover - thin wrapper
    sys.exit(main())
