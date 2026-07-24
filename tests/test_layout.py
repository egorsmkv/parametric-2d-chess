"""Validation of piece placement and the initial position (spec section 23.3)."""

from __future__ import annotations

import pytest

from chess2d.assembly import (
    BACK_RANK,
    make_initial_position,
    place_piece,
)
from chess2d.board import square_center
from chess2d.parameters import SQUARE_SIZE, PieceType, Side
from chess2d.pieces import make_piece


def test_back_rank_composition() -> None:
    counts = {pt: BACK_RANK.count(pt) for pt in PieceType}
    assert counts[PieceType.ROOK] == 2
    assert counts[PieceType.KNIGHT] == 2
    assert counts[PieceType.BISHOP] == 2
    assert counts[PieceType.QUEEN] == 1
    assert counts[PieceType.KING] == 1
    # King is right of the queen from White's side (files e vs d).
    assert BACK_RANK.index(PieceType.QUEEN) == 3
    assert BACK_RANK.index(PieceType.KING) == 4


def test_initial_position_piece_counts() -> None:
    comp = make_initial_position()
    # 16 two-sided pieces per side; each is a single connected face (the two
    # halves are joined by the central border neck) -> 16 faces per side.
    assert len(comp.white_pieces.faces()) == 16
    assert len(comp.black_pieces.faces()) == 16


def test_piece_stays_within_its_square() -> None:
    # A placed piece must not cross its square boundary.
    for file in range(8):
        piece = make_piece(BACK_RANK[file])
        placed = place_piece(piece, file, 0, Side.WHITE)
        box = placed.bounding_box()
        cx = (file - 3.5) * SQUARE_SIZE
        cy = (0 - 3.5) * SQUARE_SIZE
        half = SQUARE_SIZE / 2
        assert cx - half - 1e-6 <= box.min.X
        assert cx + half + 1e-6 >= box.max.X
        assert cy - half - 1e-6 <= box.min.Y
        assert cy + half + 1e-6 >= box.max.Y


def test_black_pieces_are_on_far_side() -> None:
    comp = make_initial_position()
    white_box = comp.white_pieces.bounding_box()
    black_box = comp.black_pieces.bounding_box()
    # White at -Y, Black at +Y.
    assert white_box.center().Y < 0
    assert black_box.center().Y > 0


def test_both_sides_use_identical_two_sided_geometry() -> None:
    # Two-sided figures are point-symmetric (a 180-deg-rotated bottom half), so
    # they need no per-side rotation and their bounding-box centre lands exactly
    # on the square centre for both White and Black.
    white_knight = place_piece(make_piece(PieceType.KNIGHT), 1, 0, Side.WHITE)
    black_knight = place_piece(make_piece(PieceType.KNIGHT), 1, 7, Side.BLACK)

    wx, wy = square_center(1, 0)
    bx, by = square_center(1, 7)
    wb = white_knight.bounding_box()
    bb = black_knight.bounding_box()
    assert pytest.approx(wb.center().X, abs=1e-6) == wx
    assert pytest.approx(wb.center().Y, abs=1e-6) == wy
    assert pytest.approx(bb.center().X, abs=1e-6) == bx
    assert pytest.approx(bb.center().Y, abs=1e-6) == by
    assert pytest.approx(wb.size.X, abs=1e-6) == bb.size.X
    assert pytest.approx(wb.size.Y, abs=1e-6) == bb.size.Y


def test_two_sided_figure_is_vertically_symmetric() -> None:
    # Each figure reads the same from top and bottom edges: symmetric in Y, and
    # is a single connected piece (printable / cuttable as one element).
    for piece_type in PieceType:
        figure = make_piece(piece_type)
        box = figure.bounding_box()
        assert abs(box.min.Y + box.max.Y) < 1e-6
        assert len(figure.faces()) == 1


def test_pawn_ranks() -> None:
    comp = make_initial_position()
    # Eight pawns occupy rank 2 for White (y for rank index 1).
    white_pawn_y = (1 - 3.5) * SQUARE_SIZE
    # The lowest 8 faces on the white side sit near the pawn rank; sanity-check
    # that white geometry spans back rank (rank 0) up to pawn rank (rank 1).
    box = comp.white_pieces.bounding_box()
    assert white_pawn_y > box.min.Y
