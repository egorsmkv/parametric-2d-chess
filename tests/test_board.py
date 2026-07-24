"""Validation of the chessboard geometry (spec section 23.2)."""

from __future__ import annotations

from chess2d.board import is_dark_square, make_board, make_square, square_center
from chess2d.parameters import BOARD_SQUARES, SQUARE_SIZE


def test_sixtyfour_squares_split_evenly() -> None:
    board = make_board(with_border=False)
    light = board.light_squares.faces()
    dark = board.dark_squares.faces()
    assert len(light) + len(dark) == 64
    assert len(light) == 32
    assert len(dark) == 32


def test_total_playing_area() -> None:
    board = make_board(with_border=False)
    total = board.light_squares.area + board.dark_squares.area
    assert abs(total - 64 * SQUARE_SIZE**2) < 1e-6


def test_overall_playing_width() -> None:
    board = make_board(with_border=False)
    combined = board.light_squares + board.dark_squares
    box = combined.bounding_box()
    assert abs(box.size.X - BOARD_SQUARES * SQUARE_SIZE) < 1e-6
    assert abs(box.size.Y - BOARD_SQUARES * SQUARE_SIZE) < 1e-6


def test_lower_right_square_is_light() -> None:
    # h1 from White's perspective: file 7, rank 0.
    assert is_dark_square(7, 0) is False


def test_square_centers_align_to_grid() -> None:
    for file in range(BOARD_SQUARES):
        for rank in range(BOARD_SQUARES):
            x, y = square_center(file, rank)
            # Centres sit on the half-integer grid scaled by square size.
            assert abs((x / SQUARE_SIZE) - (file - 3.5)) < 1e-9
            assert abs((y / SQUARE_SIZE) - (rank - 3.5)) < 1e-9


def test_single_square_size() -> None:
    box = make_square(0, 0).bounding_box()
    assert abs(box.size.X - SQUARE_SIZE) < 1e-6
    assert abs(box.size.Y - SQUARE_SIZE) < 1e-6


def test_border_present_when_requested() -> None:
    board = make_board(with_border=True)
    assert board.border is not None
    assert board.border.area > 0


def test_optional_base_plate() -> None:
    board = make_board(with_base=True)
    assert board.base is not None
    assert board.base.volume > 0
