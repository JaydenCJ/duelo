"""The tiny Gauss-Jordan kernel: solve, invert, singularity, pivoting."""

from __future__ import annotations

import pytest

from duelo.linalg import SingularMatrixError, invert, solve


def test_solve_known_2x2_system():
    # 2x + y = 5, x + 3y = 10  ->  x = 1, y = 3
    x = solve([[2.0, 1.0], [1.0, 3.0]], [5.0, 10.0])
    assert x == pytest.approx([1.0, 3.0])


def test_invert_matches_hand_computed_inverse():
    inv = invert([[4.0, 7.0], [2.0, 6.0]])
    assert inv[0] == pytest.approx([0.6, -0.7])
    assert inv[1] == pytest.approx([-0.2, 0.4])


def test_invert_times_original_is_identity_5x5():
    matrix = [[1.0 + (i * 5 + j) % 7 + (3.0 if i == j else 0.0) for j in range(5)] for i in range(5)]
    inv = invert(matrix)
    for i in range(5):
        for j in range(5):
            prod = sum(matrix[i][k] * inv[k][j] for k in range(5))
            assert prod == pytest.approx(1.0 if i == j else 0.0, abs=1e-9)


def test_partial_pivoting_handles_zero_leading_pivot():
    # Naive elimination without pivoting would divide by zero here.
    x = solve([[0.0, 1.0], [1.0, 0.0]], [2.0, 3.0])
    assert x == pytest.approx([3.0, 2.0])


def test_singular_matrix_raises_typed_error():
    with pytest.raises(SingularMatrixError, match="singular"):
        invert([[1.0, 2.0], [2.0, 4.0]])


def test_non_square_matrix_rejected():
    with pytest.raises(ValueError, match="square"):
        invert([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
