"""Bauhaus silhouettes -- after Josef Hartwig's 1924 set.

The design principle is that the *shape states the move*: the rook is a square
because it travels on the ranks and files, the bishop a diamond because it
travels on the diagonals, the knight a stepped L, the queen a circle because it
goes everywhere, the king a cross, and the pawn the plain triangle. Nothing is
representational, so these read at any size and cut cleanly on a laser.

Unlike the turned styles, every piece here is already point-symmetric or nearly
so, which is why the registry gives this style a much larger ``fused_keep``:
cropping a square to its top fraction would throw away the very thing that
identifies it.
"""

from __future__ import annotations

from build123d import (
    BuildLine,
    BuildSketch,
    Circle,
    Line,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Sketch,
    make_face,
    mirror,
)

from ..geometry import centered, scaled


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: the triangle -- the simplest form, moving only forward.

    Hartwig's pawn is a small cube, told from the rook's larger cube by size
    alone. That cannot survive here: the two-sided and fused modes scale every
    figure to the same height, so a size-only difference disappears and the two
    become the same square. The pawn therefore takes the remaining primitive
    that is unmistakable at any scale.
    """
    with BuildSketch() as sk:
        with BuildLine():
            points = [(-10.5, -10.0), (10.5, -10.0), (0.0, 11.0)]
            for start, end in zip(points, points[1:] + points[:1], strict=True):
                Line(start, end)
        make_face()
    return scaled(centered(sk.sketch), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: the large square -- straight along the ranks and files."""
    return scaled(centered(Rectangle(24.0, 24.0)), scale)


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: a stepped L -- two squares along, one across."""
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")
    # An L built from two overlapping bars: tall upright plus a foot.
    upright = Pos(-4.0, 0.0) * Rectangle(11.0, 27.0)
    foot = Pos(2.5, -8.0) * Rectangle(24.0, 11.0)
    knight: Sketch = upright + foot
    if facing == "right":
        knight = mirror(knight, about=Plane.YZ)
    return scaled(centered(knight), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: the diamond -- a square turned onto its corner, for diagonals."""
    return scaled(centered(Rot(0, 0, 45) * Rectangle(21.0, 21.0)), scale)


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: the circle -- free in every direction."""
    return scaled(centered(Circle(15.0)), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: the cross -- the piece the whole game is played around."""
    # A bold plus sign, clearly distinct from both the square and the diamond.
    vertical = Rectangle(11.0, 34.0)
    horizontal = Rectangle(30.0, 11.0)
    return scaled(centered(vertical + horizontal), scale)
