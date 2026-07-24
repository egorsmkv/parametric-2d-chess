"""Parametric 2D silhouettes for the six chess piece types.

Every ``make_*`` function returns a :class:`~build123d.Sketch` face, authored in
millimetres, facing +Y, centred on its local origin. The silhouettes share a
common stylised base (spec section 10) so the set reads as one graphical family.
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import (
    BuildLine,
    BuildSketch,
    Line,
    Part,
    Plane,
    Pos,
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
from .parameters import PIECE_MAX_HEIGHT, PIECE_THICKNESS, PieceType

# --------------------------------------------------------------------------
# Common base (spec section 10)
# --------------------------------------------------------------------------


def make_common_base(width: float, height: float, waist_width: float) -> Sketch:
    """Stylised lower base: wide foot, narrow waist and a small upper collar.

    The parts are stacked with vertical overlap and share the centre column, so
    the union always resolves to a single connected face.
    """
    foot = rounded_bar(width, height * 0.26, 0.0)
    lower = rounded_bar(width * 0.86, height * 0.40, height * 0.18)
    waist = rounded_bar(waist_width, height * 0.30, height * 0.48)
    collar_width = waist_width + (width - waist_width) * 0.55
    collar = rounded_bar(collar_width, height * 0.24, height * 0.70)
    return foot + lower + waist + collar


# --------------------------------------------------------------------------
# Individual pieces
# --------------------------------------------------------------------------


def make_pawn(scale: float = 1.0) -> Sketch:
    """Compact pawn: rounded base, narrow neck and a clearly circular head."""
    base = make_common_base(width=22.0, height=14.0, waist_width=10.0)
    neck = rounded_bar(9.0, 15.0, 11.0)
    shoulder = rounded_bar(15.0, 5.0, 22.0, radius=2.5)
    head = disc(0.0, 30.5, 6.5)
    pawn = base + neck + shoulder + head
    return scaled(centered(pawn), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: tapered tower and exactly three front-view battlements."""
    base = make_common_base(width=28.0, height=15.0, waist_width=15.0)
    # Slightly tapered tower body.
    with BuildSketch() as tower_sk:
        with BuildLine():
            Line((-12.0, 12.0), (12.0, 12.0))
            Line((12.0, 12.0), (11.0, 30.0))
            Line((11.0, 30.0), (-11.0, 30.0))
            Line((-11.0, 30.0), (-12.0, 12.0))
        make_face()
    tower = tower_sk.sketch
    # Wide crown platform.
    platform = rounded_bar(28.0, 5.0, 29.0, radius=1.2)
    # Three merlons: the central one a touch wider than the outer pair.
    merlon_c = rounded_bar(8.0, 7.0, 33.0, radius=1.0)
    merlon_l = Pos(-9.5, 0) * rounded_bar(6.5, 7.0, 33.0, radius=1.0)
    merlon_r = Pos(9.5, 0) * rounded_bar(6.5, 7.0, 33.0, radius=1.0)
    rook = base + tower + platform + merlon_c + merlon_l + merlon_r
    return scaled(centered(rook), scale)


def _horse_profile() -> Sketch:
    """A single connected, left-facing horse-head silhouette (muzzle at -X)."""
    # Closed outline walked clockwise from the bottom-right of the neck. The
    # straight bottom segment is glued to the base and hidden by the union.
    pts = [
        (11.0, 12.0),   # bottom-right of neck
        (11.5, 24.0),   # back of neck
        (9.0, 33.0),    # crest / mane
        (5.5, 40.0),    # poll (top of head)
        (3.0, 42.0),    # ear tip
        (0.5, 39.5),    # ear notch
        (-2.5, 40.5),   # brow
        (-7.0, 37.0),   # forehead
        (-11.5, 33.0),  # top of muzzle
        (-13.0, 29.0),  # nose tip (leftmost)
        (-10.5, 26.5),  # nostril / lip
        (-6.0, 26.0),   # mouth
        (-3.0, 23.5),   # jaw
        (-5.0, 18.0),   # throat
        (-7.0, 12.0),   # bottom-left of neck
    ]
    with BuildSketch() as sk:
        with BuildLine():
            Spline(pts)
            Line(pts[-1], pts[0])
        make_face()
    return sk.sketch


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: the one strongly asymmetric piece -- a stylised horse head.

    ``facing`` selects ``"left"`` (native) or ``"right"`` (mirrored about Y).
    """
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")
    base = make_common_base(width=26.0, height=14.0, waist_width=13.0)
    horse = _horse_profile()
    knight = base + horse
    if facing == "right":
        knight = mirror(knight, about=Plane.YZ)
    return scaled(centered(knight), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: tapered body, narrow neck and a slit leaf-shaped mitre."""
    base = make_common_base(width=25.0, height=14.0, waist_width=11.0)
    with BuildSketch() as body_sk:
        with BuildLine():
            Line((-10.0, 12.0), (10.0, 12.0))
            Line((10.0, 12.0), (6.0, 26.0))
            Line((6.0, 26.0), (-6.0, 26.0))
            Line((-6.0, 26.0), (-10.0, 12.0))
        make_face()
    body = body_sk.sketch
    collar = rounded_bar(11.0, 3.0, 25.0, radius=1.0)
    # Pointed leaf-shaped mitre.
    mitre_pts = [
        (0.0, 43.0),   # top tip
        (5.5, 38.0),
        (7.5, 32.0),   # widest point
        (4.0, 28.5),
        (0.0, 27.0),   # bottom
        (-4.0, 28.5),
        (-7.5, 32.0),
        (-5.5, 38.0),
    ]
    with BuildSketch() as mitre_sk:
        with BuildLine():
            Spline(mitre_pts)
            Line(mitre_pts[-1], mitre_pts[0])
        make_face()
    mitre = mitre_sk.sketch
    bishop = base + body + collar + mitre
    # Diagonal mitre slit as a true internal opening (spec 14.3).
    slit = Pos(1.0, 35.0) * Rot(0, 0, 22) * rounded_bar(2.3, 12.0, -6.0, radius=1.1)
    bishop = bishop - slit
    return scaled(centered(bishop), scale)


def _crown_points(
    tips: list[tuple[float, float]],
    band_top: float,
    ball_radius: float,
) -> Sketch:
    """A continuous zig-zag crown polygon topped by a ball at every tip."""
    # Walk up the left side of each spike and down the right, tracing the
    # valleys between tips, then close along the band. One connected polygon.
    valley_y = band_top
    left_x = tips[0][0] - ball_radius
    right_x = tips[-1][0] + ball_radius
    up_pts: list[tuple[float, float]] = [(left_x, valley_y)]
    for i, (tx, ty) in enumerate(tips):
        up_pts.append((tx, ty))
        if i < len(tips) - 1:
            mid_x = (tx + tips[i + 1][0]) / 2
            up_pts.append((mid_x, valley_y + 2.0))
    up_pts.append((right_x, valley_y))
    with BuildSketch() as sk:
        with BuildLine():
            poly_pts = up_pts + [(right_x, valley_y - 3.0), (left_x, valley_y - 3.0)]
            for a, b in zip(poly_pts, poly_pts[1:] + poly_pts[:1], strict=True):
                Line(a, b)
        make_face()
    crown = sk.sketch
    for tx, ty in tips:
        crown = crown + disc(tx, ty, ball_radius)
    return crown


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: broad shoulder and a five-point balled crown, centre tallest."""
    base = make_common_base(width=30.0, height=15.0, waist_width=12.0)
    with BuildSketch() as body_sk:
        with BuildLine():
            Line((-8.0, 13.0), (8.0, 13.0))
            Line((8.0, 13.0), (15.5, 26.0))
            Line((15.5, 26.0), (-15.5, 26.0))
            Line((-15.5, 26.0), (-8.0, 13.0))
        make_face()
    body = body_sk.sketch
    band = rounded_bar(31.0, 5.0, 25.0, radius=1.5)
    tips = [
        (-14.0, 37.5),
        (-8.0, 40.0),
        (0.0, 43.0),
        (8.0, 40.0),
        (14.0, 37.5),
    ]
    crown = _crown_points(tips, band_top=30.0, ball_radius=2.6)
    queen = base + body + band + crown
    return scaled(centered(queen), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: broad body, rounded crown and a connected central cross."""
    base = make_common_base(width=30.0, height=15.0, waist_width=12.0)
    with BuildSketch() as body_sk:
        with BuildLine():
            Line((-8.0, 13.0), (8.0, 13.0))
            Line((8.0, 13.0), (15.5, 26.0))
            Line((15.5, 26.0), (-15.5, 26.0))
            Line((-15.5, 26.0), (-8.0, 13.0))
        make_face()
    body = body_sk.sketch
    crown = rounded_bar(29.0, 11.0, 25.0, radius=5.0)
    # Central cross, overlapping the crown so it never floats (spec 16.2).
    cross_v = rounded_bar(3.4, 12.0, 34.0, radius=1.0)
    cross_h = rounded_bar(9.0, 3.4, 38.5, radius=1.0)
    king = base + body + crown + cross_v + cross_h
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
    """Double a single figure into a two-sided token scaled to fit one square."""
    doubled = two_sided(sketch)
    height = doubled.bounding_box().size.Y
    return scaled(doubled, PIECE_MAX_HEIGHT / height)


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
