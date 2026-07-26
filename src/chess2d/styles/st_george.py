"""St. George silhouettes -- the pre-Staunton English standard.

The set most English players used before 1849: heavier and more bulbous than
Staunton, with pronounced collar rings and rounded ball finials instead of
crowns and mitres. Built from the same turned half-profiles as
:mod:`chess2d.styles.staunton`, but stouter.
"""

from __future__ import annotations

from build123d import Line, Plane, Pos, Rectangle, Rot, Sketch, Spline, mirror

from ..geometry import centered, disc, rounded_bar, scaled
from ._common import revolved


def _ring(y: float, half_width: float) -> Sketch:
    """A pronounced collar ring -- the motif that dates this style."""
    return rounded_bar(half_width * 2, 2.6, y, radius=1.2)


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: a fat ball on a ringed baluster."""

    def edges() -> None:
        Line((0.0, 0.0), (9.5, 0.0))
        Line((9.5, 0.0), (9.5, 2.4))
        Spline((9.5, 2.4), (7.6, 3.8), (8.4, 5.6), (5.6, 6.8))  # bulbous base
        Spline((5.6, 6.8), (3.6, 9.0), (3.6, 12.0))  # short stout stem
        Spline((3.6, 12.0), (5.8, 13.4), (5.4, 15.2), (3.4, 16.2))  # collar bulge
        Spline((3.4, 16.2), (6.4, 18.8), (6.6, 22.6), (3.6, 25.0), (0.0, 25.8))  # ball
        Line((0.0, 25.8), (0.0, 0.0))

    return scaled(centered(revolved(edges) + _ring(11.6, 4.2)), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: a stout ringed tower with a low castellated top."""

    def edges() -> None:
        Line((0.0, 0.0), (10.5, 0.0))
        Line((10.5, 0.0), (10.5, 2.6))
        Spline((10.5, 2.6), (8.4, 4.0), (9.4, 6.0), (7.4, 7.2))
        Spline((7.4, 7.2), (6.6, 11.0), (6.8, 15.0))  # fat body
        Line((6.8, 15.0), (8.8, 17.0))  # flare to parapet
        Line((8.8, 17.0), (8.8, 23.0))
        Line((8.8, 23.0), (0.0, 23.0))
        Line((0.0, 23.0), (0.0, 0.0))

    body = revolved(edges)
    crenel = Rectangle(3.2, 4.4)
    body = body - (Pos(-4.4, 22.0) * crenel) - (Pos(4.4, 22.0) * crenel)
    return scaled(centered(body + _ring(10.5, 6.0)), scale)


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: a rounded horse head on a stout ringed pedestal."""
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")

    def edges() -> None:
        Line((0.0, 0.0), (10.5, 0.0))
        Line((10.5, 0.0), (10.5, 2.6))
        Spline((10.5, 2.6), (8.4, 4.0), (9.4, 6.0), (7.6, 7.4))
        Spline((7.6, 7.4), (6.8, 9.6), (7.0, 11.6))
        Line((7.0, 11.6), (8.2, 12.8))
        Line((8.2, 12.8), (0.0, 12.8))
        Line((0.0, 12.8), (0.0, 0.0))

    pedestal = revolved(edges) + _ring(11.0, 5.6)
    # A rounder, chunkier head than the Staunton horse.
    head = [
        (9.5, 11.5),
        (10.5, 19.0),
        (9.0, 25.0),
        (6.0, 30.0),
        (2.5, 33.0),
        (-1.5, 32.5),
        (-3.0, 34.5),
        (-6.5, 31.0),
        (-11.0, 28.0),
        (-13.0, 25.0),
        (-10.5, 23.5),
        (-7.5, 24.0),
        (-6.0, 20.0),
        (-6.5, 15.0),
        (-4.0, 11.5),
    ]
    from build123d import BuildLine, BuildSketch, make_face  # noqa: PLC0415

    with BuildSketch() as sk:
        with BuildLine():
            Spline(head)
            Line(head[-1], head[0])
        make_face()
    knight = pedestal + sk.sketch
    if facing == "right":
        knight = mirror(knight, about=Plane.YZ)
    return scaled(centered(knight), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: a ringed body under a rounded mitre with a ball finial."""

    def edges() -> None:
        Line((0.0, 0.0), (9.5, 0.0))
        Line((9.5, 0.0), (9.5, 2.4))
        Spline((9.5, 2.4), (7.6, 3.8), (8.4, 5.6), (5.6, 6.8))
        Spline((5.6, 6.8), (3.6, 10.5), (3.6, 16.0))  # stout stem
        Spline((3.6, 16.0), (5.8, 17.4), (5.4, 19.2), (3.4, 20.2))  # collar
        Line((3.4, 20.2), (4.0, 22.0))
        Spline((4.0, 22.0), (6.6, 25.0), (6.4, 29.5), (3.4, 32.5), (1.6, 33.6))  # mitre
        Spline((1.6, 33.6), (0.9, 34.4), (1.4, 35.8), (0.0, 36.6))  # ball finial
        Line((0.0, 36.6), (0.0, 0.0))

    bishop = revolved(edges) + _ring(15.6, 4.0)
    slit = Pos(0.7, 28.0) * Rot(0, 0, 26) * rounded_bar(1.8, 8.5, -4.25, radius=0.8)
    return scaled(centered(bishop - slit), scale)


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: a tall ringed body under a single large ball (no coronet)."""

    def edges() -> None:
        Line((0.0, 0.0), (10.5, 0.0))
        Line((10.5, 0.0), (10.5, 2.6))
        Spline((10.5, 2.6), (8.4, 4.0), (9.4, 6.0), (6.4, 7.4))
        Spline((6.4, 7.4), (3.8, 12.0), (3.6, 19.0))  # tall stout stem
        Spline((3.6, 19.0), (6.0, 20.4), (5.6, 22.2), (3.6, 23.2))  # collar
        Spline((3.6, 23.2), (7.0, 25.4), (7.6, 29.2), (4.4, 31.6))  # shoulder
        Spline((4.4, 31.6), (7.2, 33.6), (7.4, 37.8), (4.0, 40.4), (0.0, 41.4))  # ball
        Line((0.0, 41.4), (0.0, 0.0))

    body = revolved(edges) + _ring(18.6, 4.4)
    return scaled(centered(body + disc(0.0, 42.0, 1.8)), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: like the queen but topped with a small ringed cross."""

    def edges() -> None:
        Line((0.0, 0.0), (10.5, 0.0))
        Line((10.5, 0.0), (10.5, 2.6))
        Spline((10.5, 2.6), (8.4, 4.0), (9.4, 6.0), (6.4, 7.4))
        Spline((6.4, 7.4), (3.8, 12.0), (3.6, 19.5))  # tall stout stem
        Spline((3.6, 19.5), (6.0, 20.9), (5.6, 22.7), (3.6, 23.7))  # collar
        Spline((3.6, 23.7), (7.0, 25.9), (7.6, 29.7), (4.4, 32.1))  # shoulder
        Spline((4.4, 32.1), (6.6, 33.9), (6.8, 36.6), (4.2, 38.4))  # domed crown
        Line((4.2, 38.4), (0.0, 38.4))
        Line((0.0, 38.4), (0.0, 0.0))

    body = revolved(edges) + _ring(19.0, 4.4)
    cross_v = rounded_bar(2.8, 9.0, 37.6, radius=1.0)
    cross_h = rounded_bar(7.0, 2.6, 40.6, radius=1.0)
    return scaled(centered(body + cross_v + cross_h), scale)
