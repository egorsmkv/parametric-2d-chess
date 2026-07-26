"""Selenus silhouettes -- the tiered German style of the 17th-19th centuries.

Instead of one smooth turned body, each piece is a "pagoda" stack of flat discs
that steps inward as it rises, and rank is read from the number of tiers and the
finial on top. Built by unioning rounded bars around a central column, which
keeps every piece a single connected face by construction.
"""

from __future__ import annotations

from build123d import Line, Plane, Pos, Rectangle, Rot, Sketch, Spline, mirror

from ..geometry import centered, disc, rounded_bar, scaled
from ._common import coronet, revolved

# Every tier is this tall; the column threading them is this wide.
TIER_HEIGHT: float = 4.0
COLUMN_WIDTH: float = 4.2


def _stack(base_width: float, widths: list[float], y0: float) -> tuple[Sketch, float]:
    """Stack tiers of the given widths, returning the sketch and the top height.

    A central column runs the full height so the tiers are never separate faces.
    """
    height = len(widths) * TIER_HEIGHT
    stack: Sketch = rounded_bar(COLUMN_WIDTH, height + 0.5, y0)
    y = y0
    for width in widths:
        stack = stack + rounded_bar(width, TIER_HEIGHT, y, radius=0.6)
        y += TIER_HEIGHT
    return stack, y


def _foot(width: float) -> Sketch:
    """The wide stepped foot every Selenus piece stands on."""

    def edges() -> None:
        Line((0.0, 0.0), (width, 0.0))
        Line((width, 0.0), (width, 2.4))
        Line((width, 2.4), (width * 0.78, 3.0))
        Line((width * 0.78, 3.0), (width * 0.78, 5.2))
        Line((width * 0.78, 5.2), (0.0, 5.2))
        Line((0.0, 5.2), (0.0, 0.0))

    return revolved(edges)


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: three tiers under a small ball."""
    body, top = _stack(9.0, [8.6, 7.4, 6.2], 5.2)
    piece = _foot(9.0) + body + disc(0.0, top + 2.4, 3.2)
    return scaled(centered(piece), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: four tiers under a wide castellated cap."""
    body, top = _stack(10.0, [9.6, 8.6, 7.4, 6.2], 5.2)
    cap = rounded_bar(9.6, 5.4, top, radius=0.6)
    crenel = Rectangle(2.6, 3.2)
    cap = cap - (Pos(-3.0, top + 4.2) * crenel) - (Pos(3.0, top + 4.2) * crenel)
    return scaled(centered(_foot(10.0) + body + cap), scale)


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: three tiers carrying an angular head."""
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")
    body, top = _stack(10.0, [9.6, 8.2, 6.8], 5.2)
    head = [
        (5.2, top),
        (6.2, top + 6.0),
        (4.6, top + 10.6),
        (1.6, top + 13.0),
        (-2.6, top + 12.2),
        (-6.0, top + 9.6),
        (-6.6, top + 6.6),
        (-4.2, top + 5.6),
        (-2.2, top + 6.0),
        (-1.6, top + 3.0),
        (-2.4, top),
    ]
    from build123d import BuildLine, BuildSketch, make_face  # noqa: PLC0415

    with BuildSketch() as sk:
        with BuildLine():
            Spline(head)
            Line(head[-1], head[0])
        make_face()
    knight = _foot(10.0) + body + sk.sketch
    if facing == "right":
        knight = mirror(knight, about=Plane.YZ)
    return scaled(centered(knight), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: four tiers under a tall pointed mitre."""
    body, top = _stack(9.0, [8.6, 7.6, 6.6, 5.6], 5.2)

    def mitre() -> None:
        Line((0.0, top), (4.6, top))
        Spline((4.6, top), (4.4, top + 4.0), (2.6, top + 8.0), (0.0, top + 10.6))
        Line((0.0, top + 10.6), (0.0, top))

    piece = _foot(9.0) + body + revolved(mitre)
    slit = Pos(0.6, top + 5.2) * Rot(0, 0, 26) * rounded_bar(1.5, 5.4, -2.7, radius=0.6)
    return scaled(centered(piece - slit), scale)


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: five tiers under a balled coronet."""
    body, top = _stack(10.0, [9.8, 8.8, 7.8, 6.8, 5.8], 5.2)
    tips = [
        (-7.0, top + 4.2),
        (-3.6, top + 6.6),
        (0.0, top + 8.2),
        (3.6, top + 6.6),
        (7.0, top + 4.2),
    ]
    crown = coronet(tips, band_top=top, ball_radius=1.9)
    return scaled(centered(_foot(10.0) + body + crown), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: six tiers -- the tallest stack -- under a coronet and cross."""
    body, top = _stack(10.6, [10.2, 9.2, 8.2, 7.2, 6.2, 5.2], 5.2)
    tips = [
        (-6.4, top + 3.8),
        (-3.2, top + 6.0),
        (0.0, top + 7.4),
        (3.2, top + 6.0),
        (6.4, top + 3.8),
    ]
    crown = coronet(tips, band_top=top, ball_radius=1.8)
    cross_v = rounded_bar(2.4, 7.0, top + 6.4, radius=0.6)
    cross_h = rounded_bar(6.0, 2.2, top + 9.0, radius=0.6)
    piece = _foot(10.6) + body + crown + cross_v + cross_h
    return scaled(centered(piece), scale)
