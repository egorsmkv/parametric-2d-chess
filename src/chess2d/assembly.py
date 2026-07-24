"""Piece placement and full initial-position composition."""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce

from build123d import Location, Pos, Rot, Sketch

from .board import BoardGeometry, make_board, square_center
from .parameters import DEFAULT_STYLE, ChessStyle, PieceType, Side
from .pieces import make_piece

# Standard back-rank order, files a..h (spec 18.1).
BACK_RANK: tuple[PieceType, ...] = (
    PieceType.ROOK,
    PieceType.KNIGHT,
    PieceType.BISHOP,
    PieceType.QUEEN,
    PieceType.KING,
    PieceType.BISHOP,
    PieceType.KNIGHT,
    PieceType.ROOK,
)


def place_piece(
    sketch: Sketch,
    file_index: int,
    rank_index: int,
    side: Side,
    square_size: float = DEFAULT_STYLE.square_size,
) -> Sketch:
    """Position a native (+Y facing) piece sketch onto a board square.

    Black pieces receive a 180 deg rotation about Z so they face White.
    """
    x, y = square_center(file_index, rank_index, square_size)
    transform: Location = Pos(x, y)
    if side is Side.BLACK:
        transform = transform * Rot(0, 0, 180)
    return transform * sketch


@dataclass(frozen=True)
class ChessComposition:
    """Full board plus grouped white and black piece layers (spec 18.4)."""

    board: BoardGeometry
    white_pieces: Sketch
    black_pieces: Sketch


def _placed_side(side: Side, style: ChessStyle) -> Sketch:
    """Build all 16 placed pieces for one side as a single compound sketch."""
    back_rank_index = 0 if side is Side.WHITE else 7
    pawn_rank_index = 1 if side is Side.WHITE else 6

    placed: list[Sketch] = []
    for file in range(8):
        piece = make_piece(BACK_RANK[file], scale=style.piece_scale)
        placed.append(place_piece(piece, file, back_rank_index, side, style.square_size))
    for file in range(8):
        pawn = make_piece(PieceType.PAWN, scale=style.piece_scale)
        placed.append(place_piece(pawn, file, pawn_rank_index, side, style.square_size))

    return reduce(lambda a, b: a + b, placed)


def make_initial_position(style: ChessStyle = DEFAULT_STYLE) -> ChessComposition:
    """Assemble the standard opening arrangement: White at -Y, Black at +Y."""
    board = make_board(
        square_size=style.square_size,
        border_width=style.border_width,
    )
    return ChessComposition(
        board=board,
        white_pieces=_placed_side(Side.WHITE, style),
        black_pieces=_placed_side(Side.BLACK, style),
    )
