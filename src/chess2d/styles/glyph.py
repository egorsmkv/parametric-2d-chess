"""Glyph silhouettes -- the flat figurine symbols used in printed chess diagrams.

The style native to a two-dimensional set: bold, blocky icons on a wide skirt
base, with the fine turned beads of a Staunton profile deliberately left out so
the shapes stay legible when they are small. Straight lines are preferred to
splines throughout -- that is what keeps this visually distinct from
:mod:`chess2d.styles.staunton` rather than a slightly smoother version of it.
"""

from __future__ import annotations

from build123d import (
    BuildLine,
    BuildSketch,
    Line,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Sketch,
    Spline,
    make_face,
    mirror,
)

from ..geometry import centered, disc, rounded_bar, scaled
from ._common import revolved

# Every glyph stands on the same wide, straight-sided skirt.
SKIRT_TOP: float = 6.5


def _skirt(half_width: float = 11.0, waist: float = 5.0) -> Sketch:
    """The wide flared base shared by every glyph."""

    def edges() -> None:
        Line((0.0, 0.0), (half_width, 0.0))  # flat underside
        Line((half_width, 0.0), (half_width, 2.2))  # straight rim
        Line((half_width, 2.2), (waist, SKIRT_TOP))  # single clean flare
        Line((waist, SKIRT_TOP), (0.0, SKIRT_TOP))
        Line((0.0, SKIRT_TOP), (0.0, 0.0))

    return revolved(edges)


def _collar(y: float, half_width: float = 6.2) -> Sketch:
    """A plain rectangular collar -- the blocky stand-in for a turned bead."""
    return rounded_bar(half_width * 2, 2.4, y, radius=0.5)


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: a bold ball on a straight neck and skirt."""
    neck = rounded_bar(7.0, 8.0, SKIRT_TOP, radius=0.6)
    piece = _skirt(9.0, 4.2) + neck + _collar(14.0, 4.8) + disc(0.0, 20.0, 6.0)
    return scaled(centered(piece), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: a square tower with three square merlons."""
    body = rounded_bar(15.0, 13.0, SKIRT_TOP, radius=0.6)
    parapet = rounded_bar(18.0, 8.0, SKIRT_TOP + 13.0, radius=0.6)
    piece = _skirt(11.0, 6.5) + body + parapet
    crenel = Rectangle(3.6, 5.0)
    top = SKIRT_TOP + 19.0
    piece = piece - (Pos(-5.0, top) * crenel) - (Pos(5.0, top) * crenel)
    return scaled(centered(piece), scale)


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: a bold horse head, flat-cut rather than sculpted."""
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")
    # Fewer, straighter segments than the Staunton horse: a poster shape.
    head = [
        (7.0, 5.0),
        (8.4, 14.0),
        (7.0, 21.0),
        (4.0, 26.0),
        (2.0, 30.0),
        (-1.0, 29.0),
        (-2.0, 31.5),
        (-6.0, 27.5),
        (-11.0, 24.0),
        (-13.5, 20.0),
        (-11.0, 18.0),
        (-8.0, 18.5),
        (-6.0, 15.0),
        (-6.5, 9.0),
        (-4.0, 5.0),
    ]
    with BuildSketch() as sk:
        with BuildLine():
            Spline(head)
            Line(head[-1], head[0])
        make_face()
    knight = _skirt(11.0, 7.0) + sk.sketch
    if facing == "right":
        knight = mirror(knight, about=Plane.YZ)
    return scaled(centered(knight), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: a straight-sided mitre with a bold slit."""
    stem = rounded_bar(7.5, 7.0, SKIRT_TOP, radius=0.6)

    def mitre() -> None:
        Line((0.0, 13.5), (7.4, 13.5))
        Line((7.4, 13.5), (6.0, 22.0))  # straight taper, no spline
        Line((6.0, 22.0), (2.6, 28.0))
        Line((2.6, 28.0), (0.0, 30.5))
        Line((0.0, 30.5), (0.0, 13.5))

    piece = _skirt(9.5, 4.6) + stem + revolved(mitre) + disc(0.0, 31.5, 2.4)
    slit = Pos(1.0, 23.0) * Rot(0, 0, 30) * rounded_bar(2.2, 8.0, -4.0, radius=0.8)
    return scaled(centered(piece - slit), scale)


def _spiked_crown(y: float, points: int, half_width: float, height: float) -> Sketch:
    """A pointed crown: triangular spikes on a solid band.

    Pointed rather than square-topped on purpose -- square merlons read as a
    rook's crenellations, which would make the queen look like a second rook.
    """
    band = rounded_bar(half_width * 2, 3.2, y, radius=0.5)
    with BuildSketch() as sk:
        with BuildLine():
            base = y + 2.4
            step = (half_width * 2) / points
            pts: list[tuple[float, float]] = [(-half_width, base)]
            for index in range(points):
                left = -half_width + index * step
                peak = left + step / 2
                # Centre and outer spikes stand taller, as in the printed symbol.
                tall = height if index in (0, points - 1, points // 2) else height * 0.7
                pts.append((peak, base + tall))
                pts.append((left + step, base))
            pts.append((half_width, base - 2.0))
            pts.append((-half_width, base - 2.0))
            for start, end in zip(pts, pts[1:] + pts[:1], strict=True):
                Line(start, end)
        make_face()
    return band + sk.sketch


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: a five-pointed spiked crown on a straight body."""
    body = rounded_bar(9.0, 9.0, SKIRT_TOP, radius=0.6)
    shoulder = rounded_bar(15.0, 3.2, SKIRT_TOP + 9.0, radius=0.6)
    crown = _spiked_crown(SKIRT_TOP + 12.2, points=5, half_width=8.0, height=8.0)
    piece = _skirt(10.5, 5.4) + body + shoulder + crown
    return scaled(centered(piece), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: a crown band carrying a bold cross."""
    body = rounded_bar(9.5, 9.5, SKIRT_TOP, radius=0.6)
    shoulder = rounded_bar(15.5, 3.4, SKIRT_TOP + 9.5, radius=0.6)
    band = rounded_bar(16.0, 3.2, SKIRT_TOP + 12.9, radius=0.5)
    cross_v = rounded_bar(3.4, 12.0, SKIRT_TOP + 15.5, radius=0.5)
    cross_h = rounded_bar(9.0, 3.2, SKIRT_TOP + 19.5, radius=0.5)
    piece = _skirt(11.0, 5.8) + body + shoulder + band + cross_v + cross_h
    return scaled(centered(piece), scale)
