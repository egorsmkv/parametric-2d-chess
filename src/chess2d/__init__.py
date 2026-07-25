"""Parametric 2D chess set generated with build123d.

Public API surface:

* :mod:`chess2d.parameters` -- dimensions, enums, :class:`ChessStyle`.
* :mod:`chess2d.pieces` -- the six ``make_*`` silhouette generators.
* :mod:`chess2d.board` -- :func:`make_board` and square helpers.
* :mod:`chess2d.assembly` -- :func:`make_initial_position` and placement.
* :mod:`chess2d.export` -- SVG/DXF/STEP/STL writers and :func:`generate_all`.
* :mod:`chess2d.bambu` -- 3MF print plates and Bambu Studio slicing.
* :mod:`chess2d.estimate` -- 3D-printing material estimates.
* :mod:`chess2d.report` -- the material-estimate PDF (needs the ``app`` extra).
"""

from __future__ import annotations

from .assembly import (
    BACK_RANK,
    ChessComposition,
    make_initial_position,
    place_piece,
)
from .bambu import (
    PRINTERS,
    PlateContents,
    PlateLayout,
    Printer,
    export_plate_3mf,
    find_bambu_studio,
    slice_with_bambu_studio,
)
from .board import (
    BoardGeometry,
    is_dark_square,
    make_board,
    make_square,
    square_center,
)
from .estimate import (
    MATERIALS,
    Material,
    PartEstimate,
    PrintSettings,
    SetEstimate,
    estimate_set,
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
    "MATERIALS",
    "PLAYING_SIZE",
    "PRINTERS",
    "SQUARE_SIZE",
    "BoardGeometry",
    "ChessComposition",
    "ChessStyle",
    "Material",
    "PartEstimate",
    "PlateContents",
    "PlateLayout",
    "PrintSettings",
    "Printer",
    "FigureMode",
    "PieceGeometry",
    "PieceType",
    "SetEstimate",
    "Side",
    "estimate_set",
    "export_plate_3mf",
    "find_bambu_studio",
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
    "slice_with_bambu_studio",
    "square_center",
]
