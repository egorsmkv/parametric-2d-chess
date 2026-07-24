"""Master dimensions, enums and style configuration for the 2D chess set.

All dimensions are in millimetres. The coordinate system is:

* X: left to right.
* Y: bottom to top.
* Z: perpendicular to the board.
* Board centre: ``(0, 0, 0)``.
* White side: negative Y. Black side: positive Y.
* Every piece is authored facing toward positive Y with its local origin at
  the centre of its bounding square.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# --------------------------------------------------------------------------
# Core data model
# --------------------------------------------------------------------------


class PieceType(Enum):
    """The six kinds of chess piece."""

    PAWN = "pawn"
    ROOK = "rook"
    KNIGHT = "knight"
    BISHOP = "bishop"
    QUEEN = "queen"
    KING = "king"


class Side(Enum):
    """Piece colour / side of the board."""

    WHITE = "white"
    BLACK = "black"


# --------------------------------------------------------------------------
# Master dimensions (see spec section 5)
# --------------------------------------------------------------------------

SQUARE_SIZE: float = 50.0
BOARD_SQUARES: int = 8
BORDER_WIDTH: float = 10.0

# Parametric relationships (spec 5.1).
PLAYING_SIZE: float = BOARD_SQUARES * SQUARE_SIZE  # 400.0
BOARD_SIZE: float = PLAYING_SIZE + 2 * BORDER_WIDTH  # 420.0

PIECE_MAX_WIDTH: float = 38.0
PIECE_MAX_HEIGHT: float = 44.0
OUTLINE_WIDTH: float = 1.4

BOARD_THICKNESS: float = 3.0
PIECE_THICKNESS: float = 2.0

# Display Z offsets (spec 19) -- for CAD preview only, exports stay coplanar.
BOARD_Z: float = 0.00
PIECE_FILL_Z: float = 0.05
PIECE_OUTLINE_Z: float = 0.10

# --------------------------------------------------------------------------
# Display colours (spec 19)
# --------------------------------------------------------------------------

LIGHT_SQUARE_COLOR: tuple[float, float, float] = (0.92, 0.93, 0.80)
DARK_SQUARE_COLOR: tuple[float, float, float] = (0.49, 0.61, 0.34)
WHITE_FILL_COLOR: tuple[float, float, float] = (0.96, 0.96, 0.94)
WHITE_OUTLINE_COLOR: tuple[float, float, float] = (0.20, 0.20, 0.20)
BLACK_FILL_COLOR: tuple[float, float, float] = (0.27, 0.27, 0.27)
BLACK_OUTLINE_COLOR: tuple[float, float, float] = (0.10, 0.10, 0.10)


# --------------------------------------------------------------------------
# Per-piece nominal dimensions (spec sections 11-16)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PieceDims:
    """Nominal (unscaled) target dimensions of a single piece silhouette."""

    width: float
    height: float


PIECE_DIMS: dict[PieceType, PieceDims] = {
    PieceType.PAWN: PieceDims(25.0, 38.0),
    PieceType.ROOK: PieceDims(31.0, 40.0),
    PieceType.KNIGHT: PieceDims(31.0, 42.0),
    PieceType.BISHOP: PieceDims(28.0, 42.0),
    PieceType.QUEEN: PieceDims(34.0, 44.0),
    PieceType.KING: PieceDims(34.0, 46.0),
}


# --------------------------------------------------------------------------
# Style configuration (spec 22.1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ChessStyle:
    """Bundle of tunable parameters for a generated chess set."""

    square_size: float = SQUARE_SIZE
    border_width: float = BORDER_WIDTH
    outline_width: float = OUTLINE_WIDTH
    piece_scale: float = 1.0
    piece_thickness: float = PIECE_THICKNESS
    board_thickness: float = BOARD_THICKNESS


DEFAULT_STYLE = ChessStyle()
