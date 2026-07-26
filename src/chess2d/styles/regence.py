"""Regence silhouettes -- the early 19th-century French cafe style.

Much taller and thinner than Staunton: long slender stems, sharply stacked
collar rings and small heads, so the whole set reads as elongated. Built from
the same turned half-profiles as :mod:`chess2d.styles.staunton`.
"""

from __future__ import annotations

from build123d import Line, Plane, Pos, Rectangle, Rot, Sketch, Spline, mirror

from ..geometry import centered, disc, rounded_bar, scaled
from ._common import coronet, revolved


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: narrow foot, a long thin stem and a small ball."""

    def edges() -> None:
        Line((0.0, 0.0), (7.0, 0.0))
        Line((7.0, 0.0), (7.0, 1.6))
        Spline((7.0, 1.6), (5.2, 2.6), (6.0, 4.0), (3.6, 4.8))  # tight base bead
        Spline((3.6, 4.8), (2.0, 9.0), (1.9, 17.0))  # long slender stem
        Spline((1.9, 17.0), (3.6, 18.0), (3.4, 19.6), (2.0, 20.4))  # collar ring
        Line((2.0, 20.4), (1.7, 21.6))
        Spline((1.7, 21.6), (3.6, 23.0), (3.7, 25.6), (2.1, 27.2), (0.0, 27.8))
        Line((0.0, 27.8), (0.0, 0.0))

    return scaled(centered(revolved(edges)), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: slim tower on a tall stem, with a narrow castellated top."""

    def edges() -> None:
        Line((0.0, 0.0), (7.6, 0.0))
        Line((7.6, 0.0), (7.6, 1.8))
        Spline((7.6, 1.8), (5.6, 2.8), (6.4, 4.4), (4.2, 5.4))
        Spline((4.2, 5.4), (3.0, 10.0), (3.2, 17.0))  # tall slim body
        Spline((3.2, 17.0), (4.8, 18.2), (4.6, 19.8), (3.8, 20.6))  # collar
        Line((3.8, 20.6), (6.2, 22.4))  # flare to parapet
        Line((6.2, 22.4), (6.2, 28.2))
        Line((6.2, 28.2), (0.0, 28.2))
        Line((0.0, 28.2), (0.0, 0.0))

    body = revolved(edges)
    crenel = Rectangle(2.4, 3.6)
    body = body - (Pos(-3.2, 27.6) * crenel) - (Pos(3.2, 27.6) * crenel)
    return scaled(centered(body), scale)


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: a compact wedge head on the tall Regence stem."""
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")

    def edges() -> None:
        Line((0.0, 0.0), (7.6, 0.0))
        Line((7.6, 0.0), (7.6, 1.8))
        Spline((7.6, 1.8), (5.6, 2.8), (6.4, 4.4), (4.2, 5.4))
        Spline((4.2, 5.4), (3.0, 10.0), (3.2, 16.0))  # tall stem
        Line((3.2, 16.0), (4.6, 17.4))  # collar out
        Line((4.6, 17.4), (0.0, 17.4))
        Line((0.0, 17.4), (0.0, 0.0))

    pedestal = revolved(edges)
    # A slimmer, more angular head than the Staunton horse -- Regence knights are
    # small and wedge-like rather than sculpted.
    head = [
        (5.0, 16.0),
        (5.8, 22.0),
        (4.6, 26.4),
        (2.4, 29.6),
        (-0.6, 31.2),
        (-4.2, 30.0),
        (-6.4, 27.6),
        (-7.0, 24.6),
        (-5.0, 23.4),
        (-3.0, 23.8),
        (-2.0, 21.0),
        (-2.6, 17.6),
        (-1.0, 16.0),
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
    """Bishop: very tall stem under a small pointed mitre."""

    def edges() -> None:
        Line((0.0, 0.0), (7.0, 0.0))
        Line((7.0, 0.0), (7.0, 1.6))
        Spline((7.0, 1.6), (5.2, 2.6), (6.0, 4.2), (3.6, 5.2))
        Spline((3.6, 5.2), (2.1, 11.0), (2.0, 21.0))  # very long stem
        Spline((2.0, 21.0), (3.7, 22.2), (3.5, 23.8), (2.1, 24.6))  # collar ring
        Line((2.1, 24.6), (2.5, 26.0))
        Spline((2.5, 26.0), (4.6, 28.4), (4.8, 32.2), (2.6, 35.0), (0.0, 36.6))
        Line((0.0, 36.6), (0.0, 0.0))

    bishop = revolved(edges)
    slit = Pos(0.6, 31.0) * Rot(0, 0, 26) * rounded_bar(1.5, 7.0, -3.5, radius=0.7)
    return scaled(centered(bishop - slit), scale)


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: tall stem, narrow shoulder and a fine many-pointed coronet."""

    def edges() -> None:
        Line((0.0, 0.0), (8.0, 0.0))
        Line((8.0, 0.0), (8.0, 1.8))
        Spline((8.0, 1.8), (6.0, 2.9), (6.8, 4.6), (4.4, 5.8))
        Spline((4.4, 5.8), (2.5, 12.0), (2.4, 22.0))  # long slender stem
        Spline((2.4, 22.0), (4.2, 23.2), (4.0, 24.8), (2.6, 25.6))  # collar ring
        Spline((2.6, 25.6), (5.6, 27.0), (7.2, 29.0), (7.0, 30.6))  # narrow shoulder
        Line((7.0, 30.6), (0.0, 30.6))
        Line((0.0, 30.6), (0.0, 0.0))

    body = revolved(edges)
    tips = [
        (-6.6, 34.6),
        (-3.4, 37.0),
        (0.0, 38.8),
        (3.4, 37.0),
        (6.6, 34.6),
    ]
    return scaled(centered(body + coronet(tips, band_top=30.6, ball_radius=1.7)), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: the tallest piece -- long stem, small crown and a slim cross."""

    def edges() -> None:
        Line((0.0, 0.0), (8.0, 0.0))
        Line((8.0, 0.0), (8.0, 1.8))
        Spline((8.0, 1.8), (6.0, 2.9), (6.8, 4.6), (4.4, 5.8))
        Spline((4.4, 5.8), (2.5, 12.0), (2.4, 23.0))  # long slender stem
        Spline((2.4, 23.0), (4.2, 24.2), (4.0, 25.8), (2.6, 26.6))  # collar ring
        Spline((2.6, 26.6), (5.4, 28.2), (6.6, 30.4), (6.3, 32.2))  # shoulder
        Line((6.3, 32.2), (6.0, 33.6))  # crown band
        Spline((6.0, 33.6), (4.6, 35.0), (2.4, 35.8), (0.0, 36.0))  # small dome
        Line((0.0, 36.0), (0.0, 0.0))

    body = revolved(edges)
    cross_v = rounded_bar(2.0, 8.0, 34.8, radius=0.6)
    cross_h = rounded_bar(5.4, 1.9, 37.6, radius=0.6)
    return scaled(centered(body + cross_v + cross_h), scale)


# Keep the shared helper importable from every style module.
__all__ = [
    "disc",
    "make_bishop",
    "make_king",
    "make_knight",
    "make_pawn",
    "make_queen",
    "make_rook",
]
