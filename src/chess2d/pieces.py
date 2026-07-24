"""Parametric 2D silhouettes for the six chess piece types.

Every ``make_*`` function returns a :class:`~build123d.Sketch` face, authored in
millimetres, facing +Y, centred on its local origin. The symmetric pieces are
built from smooth turned half-profiles (mirrored about the Y-axis), giving
realistic Staunton-style silhouettes -- flared foot, base bead, concave stem,
collar bead and a distinctive top -- while the knight is a stylised horse head
on a turned pedestal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from build123d import (
    BuildLine,
    BuildSketch,
    Line,
    Part,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Shape,
    Sketch,
    Spline,
    extrude,
    make_face,
    mirror,
)

from .geometry import (
    centered,
    disc,
    outline_ring,
    outline_wires,
    rounded_bar,
    scaled,
    two_sided,
)
from .parameters import PIECE_THICKNESS, SQUARE_SIZE, PieceType

# Two-sided figures are scaled so each nearly fills its square (a small margin
# keeps neighbouring ranks from touching).
TWO_SIDED_FILL_HEIGHT: float = SQUARE_SIZE * 0.94

# --------------------------------------------------------------------------
# Common base (spec section 10)
# --------------------------------------------------------------------------


def make_common_base(width: float, height: float, waist_width: float) -> Sketch:
    """Stylised lower base: wide foot, narrow waist and a small upper collar.

    Retained for API compatibility (spec section 10). The individual pieces are
    built from smooth turned half-profiles rather than from this stacked base.
    """
    foot = rounded_bar(width, height * 0.26, 0.0)
    lower = rounded_bar(width * 0.86, height * 0.40, height * 0.18)
    waist = rounded_bar(waist_width, height * 0.30, height * 0.48)
    collar_width = waist_width + (width - waist_width) * 0.55
    collar = rounded_bar(collar_width, height * 0.24, height * 0.70)
    return foot + lower + waist + collar


# --------------------------------------------------------------------------
# Turned-profile helpers
# --------------------------------------------------------------------------


def _revolved(build_right_edges: Callable[[], None]) -> Sketch:
    """Build a symmetric silhouette from a right-hand half profile.

    ``build_right_edges`` populates a ``BuildLine`` with a closed loop that runs
    up the right-hand side of the piece (x >= 0) and returns down the Y-axis, so
    mirroring it about the YZ plane yields the full turned profile as one face --
    like the silhouette of a piece turned on a lathe.
    """
    with BuildSketch() as sk:
        with BuildLine():
            build_right_edges()
        make_face()
    half = sk.sketch
    return half + mirror(half, about=Plane.YZ)


def _coronet(
    tips: list[tuple[float, float]],
    band_top: float,
    ball_radius: float,
) -> Sketch:
    """A continuous zig-zag crown polygon topped by a ball at every tip."""
    valley_y = band_top
    left_x = tips[0][0] - ball_radius
    right_x = tips[-1][0] + ball_radius
    up_pts: list[tuple[float, float]] = [(left_x, valley_y)]
    for i, (tx, ty) in enumerate(tips):
        up_pts.append((tx, ty))
        if i < len(tips) - 1:
            mid_x = (tx + tips[i + 1][0]) / 2
            up_pts.append((mid_x, valley_y + 2.5))
    up_pts.append((right_x, valley_y))
    with BuildSketch() as sk:
        with BuildLine():
            poly_pts = up_pts + [(right_x, valley_y - 3.5), (left_x, valley_y - 3.5)]
            for a, b in zip(poly_pts, poly_pts[1:] + poly_pts[:1], strict=True):
                Line(a, b)
        make_face()
    crown = sk.sketch
    for tx, ty in tips:
        crown = crown + disc(tx, ty, ball_radius)
    return crown


# --------------------------------------------------------------------------
# Individual pieces (realistic Staunton-style turned silhouettes)
# --------------------------------------------------------------------------


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: flared foot, base bead, concave stem, collar and a spherical head."""

    def edges() -> None:
        Line((0.0, 0.0), (9.0, 0.0))               # foot underside
        Line((9.0, 0.0), (9.0, 2.0))               # foot rim
        Spline((9.0, 2.0), (7.0, 3.3), (8.2, 4.9), (5.2, 6.2))   # base bead
        Spline((5.2, 6.2), (2.9, 9.0), (2.7, 12.6))              # concave stem
        Spline((2.7, 12.6), (5.2, 14.1), (4.7, 16.0), (2.7, 17.2))  # collar bead
        Line((2.7, 17.2), (2.3, 18.6))             # neck
        Spline((2.3, 18.6), (5.2, 20.6), (5.4, 23.8), (3.0, 26.4), (0.0, 27.4))  # head
        Line((0.0, 27.4), (0.0, 0.0))              # axis
    return scaled(centered(_revolved(edges)), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: turned body rising to a castellated top with three merlons."""

    def edges() -> None:
        Line((0.0, 0.0), (10.0, 0.0))              # foot underside
        Line((10.0, 0.0), (10.0, 2.2))             # foot rim
        Spline((10.0, 2.2), (7.8, 3.4), (9.0, 5.2), (7.0, 6.4))   # base bead
        Spline((7.0, 6.4), (5.7, 9.5), (5.9, 13.0))               # slim tapered body
        Spline((5.9, 13.0), (7.4, 14.2), (7.1, 15.8), (6.4, 16.6))  # collar
        Line((6.4, 16.6), (9.0, 18.6))             # flare out to the parapet
        Line((9.0, 18.6), (9.0, 25.0))             # tower wall
        Line((9.0, 25.0), (0.0, 25.0))             # top of the parapet
        Line((0.0, 25.0), (0.0, 0.0))              # axis
    body = _revolved(edges)
    # Two crenels cut into the parapet leave three merlons in the front view.
    crenel = Rectangle(3.4, 4.6)
    body = body - (Pos(-4.6, 24.0) * crenel) - (Pos(4.6, 24.0) * crenel)
    return scaled(centered(body), scale)


def _horse_profile() -> Sketch:
    """A single connected, left-facing horse-head silhouette (muzzle at -X)."""
    # Outline walked clockwise from the bottom-right of the neck; the straight
    # bottom segment is glued onto the turned base by the union.
    outline = [
        (10.5, 9.0),    # bottom-right of neck
        (11.5, 20.0),   # back of neck
        (10.5, 27.0),   # crest
        (8.5, 33.0),    # start of mane
        (6.5, 37.5),    # mane bump
        (5.0, 40.5),    # poll
        (3.2, 42.5),    # rear ear tip
        (1.6, 40.0),    # between the ears
        (0.0, 42.0),    # front ear tip
        (-2.5, 39.0),   # forehead
        (-5.5, 36.5),   # brow
        (-9.5, 34.0),   # bridge of the nose
        (-12.5, 31.0),  # top of the muzzle
        (-13.2, 28.2),  # nose tip (leftmost)
        (-11.5, 26.6),  # nostril
        (-9.5, 26.9),   # lip
        (-7.5, 25.2),   # mouth / chin
        (-6.0, 22.5),   # jaw
        (-6.6, 18.0),   # throat
        (-6.0, 12.5),   # front of neck
        (-4.0, 9.0),    # bottom-left of neck
    ]
    with BuildSketch() as sk:
        with BuildLine():
            Spline(outline)
            Line(outline[-1], outline[0])
        make_face()
    return sk.sketch


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: a turned pedestal carrying a stylised horse head.

    ``facing`` selects ``"left"`` (native) or ``"right"`` (mirrored about Y).
    """
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")

    def edges() -> None:
        Line((0.0, 0.0), (10.0, 0.0))              # foot underside
        Line((10.0, 0.0), (10.0, 2.2))             # foot rim
        Spline((10.0, 2.2), (7.8, 3.4), (9.0, 5.2), (7.2, 6.5))   # base bead
        Spline((7.2, 6.5), (6.2, 8.5), (6.6, 10.5))               # short pedestal stem
        Line((6.6, 10.5), (7.6, 11.5))             # collar out
        Line((7.6, 11.5), (0.0, 11.5))             # pedestal top
        Line((0.0, 11.5), (0.0, 0.0))              # axis
    pedestal = _revolved(edges)
    knight = pedestal + _horse_profile()
    if facing == "right":
        knight = mirror(knight, about=Plane.YZ)
    return scaled(centered(knight), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: slender turned body, a mitre with a finial and a diagonal slit."""

    def edges() -> None:
        Line((0.0, 0.0), (9.0, 0.0))               # foot underside
        Line((9.0, 0.0), (9.0, 2.0))               # foot rim
        Spline((9.0, 2.0), (7.0, 3.2), (8.0, 4.9), (5.3, 6.0))    # base bead
        Spline((5.3, 6.0), (2.9, 9.5), (2.7, 15.5))               # tall slender stem
        Spline((2.7, 15.5), (4.9, 16.8), (4.4, 18.6), (2.7, 19.6))  # collar bead
        Line((2.7, 19.6), (3.1, 21.2))             # mitre base flare
        Spline((3.1, 21.2), (6.2, 23.8), (6.6, 28.4), (4.1, 32.4), (2.0, 34.4))  # mitre
        Spline((2.0, 34.4), (1.1, 35.2), (1.6, 36.6), (0.0, 37.4))  # finial ball
        Line((0.0, 37.4), (0.0, 0.0))              # axis
    bishop = _revolved(edges)
    # Diagonal mitre slit as a true internal opening (spec 14.3).
    slit = Pos(0.8, 29.0) * Rot(0, 0, 26) * rounded_bar(1.9, 9.5, -4.75, radius=0.9)
    return scaled(centered(bishop - slit), scale)


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: tall turned body, a flared shoulder and a balled five-point coronet."""

    def edges() -> None:
        Line((0.0, 0.0), (11.0, 0.0))              # foot underside
        Line((11.0, 0.0), (11.0, 2.2))             # foot rim
        Spline((11.0, 2.2), (8.6, 3.5), (9.7, 5.3), (6.7, 6.7))   # base bead
        Spline((6.7, 6.7), (3.5, 11.0), (3.3, 17.5))              # slender concave stem
        Spline((3.3, 17.5), (5.8, 18.9), (5.2, 20.6), (3.5, 21.6))  # collar bead
        Spline((3.5, 21.6), (7.6, 23.2), (10.2, 25.6), (10.0, 27.6))  # flaring shoulder
        Line((10.0, 27.6), (0.0, 27.6))            # coronet seat
        Line((0.0, 27.6), (0.0, 0.0))              # axis
    body = _revolved(edges)
    tips = [
        (-9.6, 33.0),
        (-4.9, 36.2),
        (0.0, 38.6),
        (4.9, 36.2),
        (9.6, 33.0),
    ]
    coronet = _coronet(tips, band_top=27.6, ball_radius=2.4)
    return scaled(centered(body + coronet), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: tall turned body, a domed crown and a connected central cross."""

    def edges() -> None:
        Line((0.0, 0.0), (11.0, 0.0))              # foot underside
        Line((11.0, 0.0), (11.0, 2.2))             # foot rim
        Spline((11.0, 2.2), (8.6, 3.5), (9.7, 5.3), (6.7, 6.7))   # base bead
        Spline((6.7, 6.7), (3.5, 11.0), (3.3, 18.0))              # slender concave stem
        Spline((3.3, 18.0), (5.8, 19.4), (5.2, 21.1), (3.5, 22.1))  # collar bead
        Spline((3.5, 22.1), (7.8, 24.0), (9.4, 27.0), (9.0, 29.4))  # shoulder to crown
        Line((9.0, 29.4), (8.6, 31.2))             # crown band
        Spline((8.6, 31.2), (6.8, 33.2), (3.6, 34.2), (0.0, 34.4))  # domed crown top
        Line((0.0, 34.4), (0.0, 0.0))              # axis
    body = _revolved(edges)
    # Central cross, overlapping the dome so it never floats (spec 16.2).
    cross_v = rounded_bar(3.0, 10.0, 33.0, radius=0.9)
    cross_h = rounded_bar(7.8, 2.8, 36.6, radius=0.9)
    king = body + cross_v + cross_h
    return scaled(centered(king), scale)


# --------------------------------------------------------------------------
# Dispatch, geometry bundle and thin solids
# --------------------------------------------------------------------------

_GENERATORS = {
    PieceType.PAWN: make_pawn,
    PieceType.ROOK: make_rook,
    PieceType.KNIGHT: make_knight,
    PieceType.BISHOP: make_bishop,
    PieceType.QUEEN: make_queen,
    PieceType.KING: make_king,
}


def _fit_two_sided(sketch: Sketch) -> Sketch:
    """Double a single figure into a two-sided token that nearly fills a square.

    Each piece is scaled individually so its two-sided figure fills the square to
    ``TWO_SIDED_FILL_HEIGHT`` -- maximising how large and legible the pieces look
    on the board (every piece is sized to the same generous height).
    """
    doubled = two_sided(sketch)
    height = doubled.bounding_box().size.Y
    return scaled(doubled, TWO_SIDED_FILL_HEIGHT / height)


def make_piece(
    piece_type: PieceType,
    scale: float = 1.0,
    mirrored: bool = False,
    two_sided_figure: bool = True,
) -> Sketch:
    """Unified dispatcher returning the filled 2D face for any piece type.

    By default the figure is *two-sided*: the silhouette is fused with its
    vertical mirror so it reads upright from both edges of the board (matching a
    flat token that both players view). Pass ``two_sided_figure=False`` for the
    plain single-sided silhouette.
    """
    if piece_type is PieceType.KNIGHT:
        sketch = make_knight(scale=1.0, facing="right" if mirrored else "left")
    else:
        sketch = _GENERATORS[piece_type](scale=1.0)
        if mirrored:
            sketch = centered(mirror(sketch, about=Plane.YZ))
    if two_sided_figure:
        sketch = _fit_two_sided(sketch)
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
    two_sided_figure: bool = True,
) -> PieceGeometry:
    """Bundle the fill face, an outline and an optional thin solid for a piece."""
    fill = make_piece(
        piece_type, scale=scale, mirrored=mirrored, two_sided_figure=two_sided_figure
    )
    ring = outline_ring(fill, outline_width)
    outline: Shape = ring if ring is not None else outline_wires(fill)
    solid = extrude(fill, amount=thickness) if with_solid else None
    return PieceGeometry(fill=fill, outline=outline, optional_solid=solid)


def make_piece_solid(
    piece_type: PieceType,
    thickness: float = PIECE_THICKNESS,
    scale: float = 1.0,
    two_sided_figure: bool = True,
) -> Part:
    """Extrude a piece silhouette into a thin flat token (spec section 20)."""
    sketch = make_piece(piece_type, scale=scale, two_sided_figure=two_sided_figure)
    return extrude(sketch, amount=thickness)
