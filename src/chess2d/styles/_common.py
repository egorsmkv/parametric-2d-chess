"""Authoring helpers shared by the piece styles.

Pure geometry, like :mod:`chess2d.geometry`, but specific to composing a piece
silhouette: a lathe-style turned profile and a balled coronet.
"""

from __future__ import annotations

from collections.abc import Callable

from build123d import (
    BuildLine,
    BuildSketch,
    Line,
    Plane,
    Sketch,
    make_face,
    mirror,
)

from ..geometry import disc


def revolved(build_right_edges: Callable[[], None]) -> Sketch:
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


def coronet(
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
            poly_pts = [*up_pts, (right_x, valley_y - 3.5), (left_x, valley_y - 3.5)]
            for a, b in zip(poly_pts, poly_pts[1:] + poly_pts[:1], strict=True):
                Line(a, b)
        make_face()
    crown = sk.sketch
    for tx, ty in tips:
        crown = crown + disc(tx, ty, ball_radius)
    return crown
