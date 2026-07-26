"""Dispatch from a piece type and style to a 2D silhouette, and thin solids.

The silhouettes themselves live in :mod:`chess2d.styles`; this module selects a
style's generator, composes the result for the chosen :class:`FigureMode` and
sizes it to the board.

The six Staunton ``make_*`` generators are re-exported here for backwards
compatibility -- they were originally defined in this module and remain the
default style.
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import Part, Plane, Shape, Sketch, extrude, mirror

from .geometry import centered, fused_two_sided, outline_ring, outline_wires, scaled, two_sided
from .parameters import (
    PIECE_THICKNESS,
    SQUARE_SIZE,
    FigureMode,
    PieceStyle,
    PieceType,
)
from .styles import STYLES
from .styles.staunton import (
    make_bishop,
    make_common_base,
    make_king,
    make_knight,
    make_pawn,
    make_queen,
    make_rook,
)

# Composed figures are scaled to fill this fraction of their square (the small
# margin keeps neighbouring ranks from touching).
FIGURE_FILL_FRACTION: float = 0.94

__all__ = [
    "FIGURE_FILL_FRACTION",
    "PieceGeometry",
    "make_bishop",
    "make_common_base",
    "make_king",
    "make_knight",
    "make_pawn",
    "make_piece",
    "make_piece_geometry",
    "make_piece_solid",
    "make_queen",
    "make_rook",
]


# --------------------------------------------------------------------------
# Dispatch, geometry bundle and thin solids
# --------------------------------------------------------------------------


def _fit_to_square(figure: Sketch, square_size: float) -> Sketch:
    """Scale a composed figure so it nearly fills its square (max legibility)."""
    height = figure.bounding_box().size.Y
    return scaled(figure, square_size * FIGURE_FILL_FRACTION / height)


def make_piece(
    piece_type: PieceType,
    scale: float = 1.0,
    mirrored: bool = False,
    mode: FigureMode = FigureMode.TWO_SIDED,
    square_size: float = SQUARE_SIZE,
    style: PieceStyle = PieceStyle.STAUNTON,
) -> Sketch:
    """Unified dispatcher returning the filled 2D face for any piece type.

    ``style`` selects the visual design (see :class:`PieceStyle`); ``mode``
    selects how that figure is composed (see :class:`FigureMode`):
    ``TWO_SIDED`` (default) stacks the figure with its 180-deg rotation so each
    player reads their end; ``FUSED`` merges the identifying tops into one
    compact point-symmetric figure that reads the same for everyone; ``SINGLE``
    is the plain one-orientation silhouette.

    Figures always follow the board: they are sized against ``square_size`` so a
    smaller board yields proportionally smaller pieces. ``scale`` then applies
    the caller's own size preference on top.
    """
    spec = STYLES[style]
    if piece_type is PieceType.KNIGHT:
        sketch = spec.generators[piece_type](scale=1.0, facing="right" if mirrored else "left")
    else:
        sketch = spec.generators[piece_type](scale=1.0)
        if mirrored:
            sketch = centered(mirror(sketch, about=Plane.YZ))
    if mode is FigureMode.TWO_SIDED:
        composed = two_sided(
            sketch,
            border=spec.two_sided_border,
            neck_fraction=spec.neck_fraction,
        )
        sketch = _fit_to_square(composed, square_size)
    elif mode is FigureMode.FUSED:
        composed = fused_two_sided(sketch, keep=spec.fused_keep, overlap=spec.fused_overlap)
        sketch = _fit_to_square(composed, square_size)
    else:
        # SINGLE keeps its native relative proportions (king taller than pawn),
        # scaled with the board so the pieces still fit smaller squares.
        sketch = scaled(sketch, square_size / SQUARE_SIZE)
    return scaled(sketch, scale)


@dataclass(frozen=True)
class PieceGeometry:
    """The three forms of a single piece (spec section 7.3)."""

    fill: Sketch
    outline: Shape
    optional_solid: Part | None


def make_piece_geometry(
    piece_type: PieceType,
    scale: float = 1.0,
    mirrored: bool = False,
    outline_width: float = 1.4,
    with_solid: bool = False,
    thickness: float = PIECE_THICKNESS,
    mode: FigureMode = FigureMode.TWO_SIDED,
    square_size: float = SQUARE_SIZE,
    style: PieceStyle = PieceStyle.STAUNTON,
) -> PieceGeometry:
    """Bundle the fill face, an outline and an optional thin solid for a piece."""
    fill = make_piece(
        piece_type,
        scale=scale,
        mirrored=mirrored,
        mode=mode,
        square_size=square_size,
        style=style,
    )
    ring = outline_ring(fill, outline_width)
    outline: Shape = ring if ring is not None else outline_wires(fill)
    solid = extrude(fill, amount=thickness) if with_solid else None
    return PieceGeometry(fill=fill, outline=outline, optional_solid=solid)


def make_piece_solid(
    piece_type: PieceType,
    thickness: float = PIECE_THICKNESS,
    scale: float = 1.0,
    mode: FigureMode = FigureMode.TWO_SIDED,
    square_size: float = SQUARE_SIZE,
    style: PieceStyle = PieceStyle.STAUNTON,
) -> Part:
    """Extrude a piece silhouette into a thin flat token (spec section 20)."""
    sketch = make_piece(piece_type, scale=scale, mode=mode, square_size=square_size, style=style)
    return extrude(sketch, amount=thickness)
