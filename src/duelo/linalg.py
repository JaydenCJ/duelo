"""Tiny dense linear algebra: solve and invert via Gauss-Jordan.

Leaderboards have tens of items, not thousands, so an O(n^3) pure-Python
Gauss-Jordan elimination with partial pivoting is more than fast enough and
keeps the package free of numeric dependencies. Matrices are plain
``list[list[float]]``.
"""

from __future__ import annotations

from typing import List

Matrix = List[List[float]]

_SINGULAR_TOL = 1e-12


class SingularMatrixError(ValueError):
    """The matrix is singular (or numerically indistinguishable from it)."""


def _augmented_eliminate(matrix: Matrix, aug: Matrix) -> Matrix:
    """Run Gauss-Jordan on ``[matrix | aug]`` and return the transformed aug."""
    n = len(matrix)
    work = [list(row) + list(arow) for row, arow in zip(matrix, aug)]
    width = len(work[0])
    for col in range(n):
        # Partial pivoting: largest absolute value in the column.
        pivot_row = max(range(col, n), key=lambda r: abs(work[r][col]))
        pivot = work[pivot_row][col]
        if abs(pivot) < _SINGULAR_TOL:
            raise SingularMatrixError(f"singular matrix (pivot {pivot:.3e} at column {col})")
        if pivot_row != col:
            work[col], work[pivot_row] = work[pivot_row], work[col]
        inv_pivot = 1.0 / work[col][col]
        for j in range(col, width):
            work[col][j] *= inv_pivot
        for r in range(n):
            if r == col:
                continue
            factor = work[r][col]
            if factor != 0.0:
                for j in range(col, width):
                    work[r][j] -= factor * work[col][j]
    return [row[n:] for row in work]


def solve(matrix: Matrix, rhs: List[float]) -> List[float]:
    """Solve ``matrix @ x = rhs`` for x."""
    if len(matrix) != len(rhs):
        raise ValueError("matrix and rhs dimensions disagree")
    result = _augmented_eliminate(matrix, [[v] for v in rhs])
    return [row[0] for row in result]


def invert(matrix: Matrix) -> Matrix:
    """Return the inverse of a square matrix."""
    n = len(matrix)
    if any(len(row) != n for row in matrix):
        raise ValueError("matrix must be square")
    identity = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    return _augmented_eliminate(matrix, identity)
