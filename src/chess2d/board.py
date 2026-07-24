"""Parametric 8x8 chessboard as 2D faces with an optional border and base plate."""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce

from build123d import (
    Part,
    Pos,
    Rectangle,
    RectangleRounded,
    Sketch,
    extrude,
)

from .parameters import (
    BOARD_SIZE,
    BOARD_SQUARES,
    BOARD_THICKNESS,
    BORDER_WIDTH,
    PLAYING_SIZE,
    SQUARE_SIZE,
)


def square_center(
    file_index: int,
    rank_index: int,
    square_size: float = SQUARE_SIZE,
) -> tuple[float, float]:
    """Centre coordinate of the square at ``(file_index, rank_index)``.

    Files and ranks are 0-based; the board is centred on the origin.
    """
    x = (file_index - (BOARD_SQUARES - 1) / 2) * square_size
    y = (rank_index - (BOARD_SQUARES - 1) / 2) * square_size
    return x, y


def is_dark_square(file_index: int, rank_index: int) -> bool:
    """Colour parity. The lower-right square from White's side (h1) is light."""
    return (file_index + rank_index) % 2 == 0


def make_square(
    file_index: int,
    rank_index: int,
    square_size: float = SQUARE_SIZE,
) -> Sketch:
    """A single positioned board square face."""
    x, y = square_center(file_index, rank_index, square_size)
    return Pos(x, y) * Rectangle(square_size, square_size)


def _union(faces: list[Sketch]) -> Sketch:
    return reduce(lambda a, b: a + b, faces)


@dataclass(frozen=True)
class BoardGeometry:
    """Grouped board geometry (spec 17.4). Colours are applied by the export/preview layer."""

    light_squares: Sketch
    dark_squares: Sketch
    border: Sketch | None
    base: Part | None


def make_board(
    square_size: float = SQUARE_SIZE,
    border_width: float = BORDER_WIDTH,
    with_border: bool = True,
    with_base: bool = False,
    board_thickness: float = BOARD_THICKNESS,
) -> BoardGeometry:
    """Build the full 8x8 board grouped into light and dark square compounds."""
    light: list[Sketch] = []
    dark: list[Sketch] = []
    for rank in range(BOARD_SQUARES):
        for file in range(BOARD_SQUARES):
            square = make_square(file, rank, square_size)
            if is_dark_square(file, rank):
                dark.append(square)
            else:
                light.append(square)

    playing_size = BOARD_SQUARES * square_size

    border: Sketch | None = None
    if with_border:
        outer_size = playing_size + 2 * border_width
        outer = RectangleRounded(outer_size, outer_size, border_width * 0.5)
        inner = Rectangle(playing_size, playing_size)
        border = outer - inner

    base: Part | None = None
    if with_base:
        plate_size = playing_size + 2 * border_width if with_border else playing_size
        base = extrude(Rectangle(plate_size, plate_size), amount=board_thickness)

    return BoardGeometry(
        light_squares=_union(light),
        dark_squares=_union(dark),
        border=border,
        base=base,
    )


# Convenience constants re-exported for callers/tests.
__all__ = [
    "BOARD_SIZE",
    "PLAYING_SIZE",
    "BoardGeometry",
    "is_dark_square",
    "make_board",
    "make_square",
    "square_center",
]
