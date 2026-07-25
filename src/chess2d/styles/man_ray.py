"""Man Ray silhouettes -- after the artist's 1920s chess set.

A second geometric vocabulary, distinct from Bauhaus: Man Ray drew his pieces
from studio objects -- a sphere (pawn), a cube (rook), a cone (bishop), a
scrolled violin head (knight), a coiled spring (queen) and a stepped pyramid
(king). It reads as sculpture rather than diagram.

Every generator returns a single connected face; the shapes are chosen so no two
collapse onto each other once fitted to the same square (a cone and a pyramid
would both flatten to a plain triangle, so the pyramid is stepped and the queen
is a coil).
"""

from __future__ import annotations

from build123d import (
    BuildLine,
    BuildSketch,
    Line,
    Plane,
    Pos,
    Rectangle,
    Sketch,
    make_face,
    mirror,
)

from ..geometry import centered, disc, rounded_bar, scaled


def _polygon(points: list[tuple[float, float]]) -> Sketch:
    """A filled polygon from a list of vertices (closed automatically)."""
    with BuildSketch() as sk:
        with BuildLine():
            for start, end in zip(points, points[1:] + points[:1], strict=True):
                Line(start, end)
        make_face()
    return sk.sketch


def _plinth(half_width: float = 6.0) -> Sketch:
    """The low slab every Man Ray piece is mounted on."""
    return rounded_bar(half_width * 2, 3.0, 0.0, radius=0.3)


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: a sphere on its plinth -- the studio marble."""
    return scaled(centered(_plinth(4.5) + disc(0.0, 10.0, 8.0)), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: a cube."""
    return scaled(centered(_plinth(6.0) + rounded_bar(20.0, 20.0, 3.0, radius=0.4)), scale)


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: a scrolled head, after a violin scroll -- the one asymmetry."""
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")
    # A tapering neck that hooks over to one side, like a violin scroll. Kept a
    # simple (non-self-intersecting) closed loop so it stays one face.
    outline = [
        (3.0, 1.5),
        (4.5, 15.0),
        (3.0, 23.0),
        (-1.0, 28.0),
        (-6.0, 29.0),
        (-10.5, 26.0),
        (-12.0, 21.0),    # the nose of the scroll (leftmost)
        (-9.0, 18.5),
        (-5.5, 19.5),     # the curl's small return bump
        (-4.0, 15.0),
        (-3.0, 8.0),
        (-2.0, 1.5),
    ]
    scroll = _plinth(5.0) + _polygon(outline)
    if facing == "right":
        scroll = mirror(scroll, about=Plane.YZ)
    return scaled(centered(scroll), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: a tall smooth cone."""
    cone = _polygon([(-7.0, 3.0), (7.0, 3.0), (0.0, 34.0)])
    return scaled(centered(_plinth(5.5) + cone), scale)


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: a coiled spring -- a stack of discs on a slim core.

    A coil rather than a cone: viewed flat a cone is a plain triangle, which
    would be hard to tell from the bishop, so the queen keeps Man Ray's spring.
    """
    core = rounded_bar(3.6, 33.0, 3.0)
    piece: Sketch = _plinth(5.5) + core
    # Overlapping discs of shrinking radius climb the core like a spring.
    for index in range(7):
        y = 6.0 + index * 4.4
        radius = 6.4 - index * 0.55
        piece = piece + disc(0.0, y, radius)
    return scaled(centered(piece), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: a stepped pyramid -- a ziggurat of shrinking slabs."""
    piece: Sketch = _plinth(6.5)
    widths = [22.0, 18.0, 14.0, 10.0, 6.0]
    y = 3.0
    for width in widths:
        piece = piece + rounded_bar(width, 6.4, y, radius=0.4)
        y += 6.4
    # A small cube caps the apex.
    piece = piece + Pos(0.0, y + 1.6) * Rectangle(4.0, 4.0)
    return scaled(centered(piece), scale)
