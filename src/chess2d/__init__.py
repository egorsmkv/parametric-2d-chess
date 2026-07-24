"""Parametric 2D chess set generated with build123d.

Public API surface:

* :mod:`chess2d.parameters` -- dimensions, enums, :class:`ChessStyle`.
* :mod:`chess2d.pieces` -- the six ``make_*`` silhouette generators.
* :mod:`chess2d.board` -- :func:`make_board` and square helpers.
* :mod:`chess2d.assembly` -- :func:`make_initial_position` and placement.
* :mod:`chess2d.export` -- SVG/DXF/STEP/STL writers and :func:`generate_all`.
"""

from __future__ import annotations

from .assembly import (
    BACK_RANK,
    ChessComposition,
    make_initial_position,
    place_piece,
)
from .board import (
    BoardGeometry,
    is_dark_square,
    make_board,
    make_square,
    square_center,
)
from .export import generate_all
from .parameters import (
    BOARD_SIZE,
    PLAYING_SIZE,
    SQUARE_SIZE,
    ChessStyle,
    FigureMode,
    PieceType,
    Side,
)
from .pieces import (
    PieceGeometry,
    make_bishop,
    make_common_base,
    make_king,
    make_knight,
    make_pawn,
    make_piece,
    make_piece_geometry,
    make_piece_solid,
    make_queen,
    make_rook,
)

__all__ = [
    "BACK_RANK",
    "BOARD_SIZE",
    "PLAYING_SIZE",
    "SQUARE_SIZE",
    "BoardGeometry",
    "ChessComposition",
    "ChessStyle",
    "FigureMode",
    "PieceGeometry",
    "PieceType",
    "Side",
    "generate_all",
    "is_dark_square",
    "make_bishop",
    "make_board",
    "make_common_base",
    "make_initial_position",
    "make_king",
    "make_knight",
    "make_pawn",
    "make_piece",
    "make_piece_geometry",
    "make_piece_solid",
    "make_queen",
    "make_rook",
    "make_square",
    "place_piece",
    "square_center",
]
