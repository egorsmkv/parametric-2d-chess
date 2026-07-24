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


class PieceStyle(Enum):
    """The visual design language of the pieces.

    Independent of :class:`FigureMode`, which selects how a figure is *composed*
    on its square rather than how it is *drawn*.

    * ``STAUNTON`` -- the 1849 tournament standard; the project default.
    * ``REGENCE`` -- early 19th-c. French: very tall, slender, small heads.
    * ``SELENUS`` -- 17th-19th-c. German: tiered "pagoda" stacks of discs.
    * ``BAUHAUS`` -- Hartwig, 1924: pure primitives whose shape encodes the move.
    * ``GLYPH`` -- the flat figurine symbols used in printed chess diagrams.
    """

    STAUNTON = "staunton"
    REGENCE = "regence"
    SELENUS = "selenus"
    BAUHAUS = "bauhaus"
    GLYPH = "glyph"


class FigureMode(Enum):
    """How a piece figure is composed.

    * ``SINGLE`` -- a plain one-orientation silhouette (upside-down for the
      opponent).
    * ``TWO_SIDED`` -- the full figure plus a 180-deg-rotated copy stacked
      base-to-base and joined by a border neck; each player reads their end.
    * ``FUSED`` -- only the identifying top of the piece, merged with its
      180-deg rotation into one compact, point-symmetric figure that reads the
      same way for every player.
    """

    SINGLE = "single"
    TWO_SIDED = "two_sided"
    FUSED = "fused"


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


# Native (single-sided) target dimensions of the turned silhouettes.
PIECE_DIMS: dict[PieceType, PieceDims] = {
    PieceType.PAWN: PieceDims(18.0, 28.0),
    PieceType.ROOK: PieceDims(20.0, 26.0),
    PieceType.KNIGHT: PieceDims(25.0, 43.0),
    PieceType.BISHOP: PieceDims(18.0, 38.0),
    PieceType.QUEEN: PieceDims(24.0, 41.0),
    PieceType.KING: PieceDims(22.0, 43.0),
}


# --------------------------------------------------------------------------
# Style configuration (spec 22.1)
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Size presets
# --------------------------------------------------------------------------

#: Board presets, as the size of one square in millimetres. The full board is
#: ``8 * square_size`` plus the border, so "large" is a 520 mm playing surface.
BOARD_SIZE_PRESETS: dict[str, float] = {
    "small": 35.0,
    "medium": 50.0,
    "large": 65.0,
}

#: Figure presets, as a multiplier on the piece size within its square. Figures
#: always scale with the board first; this is the extra size preference on top.
#: "large" fills essentially the whole square (0.94 * 1.06 ~= 1.0).
FIGURE_SIZE_PRESETS: dict[str, float] = {
    "small": 0.78,
    "medium": 1.0,
    "large": 1.06,
}


@dataclass(frozen=True)
class ChessStyle:
    """Bundle of tunable parameters for a generated chess set."""

    square_size: float = SQUARE_SIZE
    border_width: float = BORDER_WIDTH
    outline_width: float = OUTLINE_WIDTH
    piece_scale: float = 1.0
    piece_thickness: float = PIECE_THICKNESS
    board_thickness: float = BOARD_THICKNESS
    # How each piece figure is composed (see :class:`FigureMode`).
    figure_mode: FigureMode = FigureMode.TWO_SIDED
    # How the pieces are drawn (see :class:`PieceStyle`).
    piece_style: PieceStyle = PieceStyle.STAUNTON


DEFAULT_STYLE = ChessStyle()
