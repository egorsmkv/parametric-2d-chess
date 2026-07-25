"""Edinburgh silhouettes -- the abstract "North Upright" style.

A 19th-century Scottish design that strips the piece down to a plain turned
column: straight cylindrical shafts stepped with a few sharp discs, and the rank
read from the shaft height and the shape of the cap rather than from any
representational top. It sits between the turned Staunton family and the pure
geometry of Bauhaus.
"""

from __future__ import annotations

from build123d import Line, Plane, Pos, Rectangle, Rot, Sketch, mirror

from ..geometry import centered, disc, rounded_bar, scaled
from ._common import revolved

# The plain disc foot every column stands on.
FOOT_HEIGHT: float = 4.5


def _column(half_width: float, top: float) -> Sketch:
    """A straight cylindrical shaft on a stepped disc foot."""

    def edges() -> None:
        Line((0.0, 0.0), (half_width + 2.5, 0.0))          # wide foot
        Line((half_width + 2.5, 0.0), (half_width + 2.5, 2.2))
        Line((half_width + 2.5, 2.2), (half_width, FOOT_HEIGHT))  # single step in
        Line((half_width, FOOT_HEIGHT), (half_width, top))        # straight shaft
        Line((half_width, top), (0.0, top))
        Line((0.0, top), (0.0, 0.0))
    return revolved(edges)


def _band(y: float, half_width: float) -> Sketch:
    """A sharp disc band around the shaft."""
    return rounded_bar(half_width * 2, 1.8, y, radius=0.3)


def _cone(y: float, half_width: float, height: float) -> Sketch:
    """A sharp cone cap rising from ``y`` to a point."""

    def edges() -> None:
        Line((0.0, y), (half_width, y))
        Line((half_width, y), (0.0, y + height))
        Line((0.0, y + height), (0.0, y))
    return revolved(edges)


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: the shortest column, capped with a ball."""
    top = 18.0
    column = _column(3.4, top)
    return scaled(centered(column + disc(0.0, top + 2.8, 3.6)), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: a broad column with a flat notched cap."""
    top = 21.0
    column = _column(4.6, top)
    cap = rounded_bar(12.0, 4.0, top, radius=0.4)
    notch = Rectangle(2.6, 3.0)
    cap = cap - (Pos(-3.4, top + 2.6) * notch) - (Pos(3.4, top + 2.6) * notch)
    return scaled(centered(column + _band(top - 2.0, 5.2) + cap), scale)


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: a column with a single angled wedge cap -- the one asymmetry."""
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")
    top = 24.0
    column = _column(4.0, top)
    # A slanted wedge: the only piece in this austere style that leans.
    wedge = [
        (-5.0, top),
        (5.0, top),
        (5.0, top + 5.0),
        (-1.0, top + 11.0),
        (-5.0, top + 9.0),
    ]
    from build123d import BuildLine, BuildSketch, make_face  # noqa: PLC0415

    with BuildSketch() as sk:
        with BuildLine():
            for start, end in zip(wedge, wedge[1:] + wedge[:1], strict=True):
                Line(start, end)
        make_face()
    knight = column + _band(top - 2.0, 4.6) + sk.sketch
    if facing == "right":
        knight = mirror(knight, about=Plane.YZ)
    return scaled(centered(knight), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: a slim column with a small pointed cap and a slit."""
    top = 28.0
    column = _column(3.2, top)

    def cap() -> None:
        Line((0.0, top), (4.0, top))
        Line((4.0, top), (0.0, top + 7.0))
        Line((0.0, top + 7.0), (0.0, top))
    piece = column + _band(top - 2.0, 4.0) + revolved(cap)
    slit = Pos(0.6, top + 3.0) * Rot(0, 0, 24) * rounded_bar(1.4, 5.0, -2.5, radius=0.5)
    return scaled(centered(piece - slit), scale)


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: a slim column tapering to a tall pointed spire."""
    top = 30.0
    column = _column(3.2, top)
    # A sharp cone, so the queen's outline narrows to a point.
    spire = _cone(top, half_width=4.6, height=12.0)
    return scaled(centered(column + _band(top - 2.2, 4.2) + spire), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: a broad column with a wide flat cross -- squat where the queen is sharp."""
    top = 30.0
    column = _column(5.2, top)                          # visibly broader shaft
    band = rounded_bar(13.0, 3.0, top, radius=0.4)
    cross_v = rounded_bar(3.0, 9.0, top + 3.0, radius=0.4)
    cross_h = rounded_bar(11.0, 2.6, top + 6.5, radius=0.4)   # wide arms
    return scaled(
        centered(column + _band(top - 2.4, 6.0) + band + cross_v + cross_h), scale
    )
