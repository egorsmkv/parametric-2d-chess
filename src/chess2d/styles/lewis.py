"""Isle of Lewis silhouettes -- after the 12th-century Norse carvings.

The most famous surviving medieval set: squat, big-headed figures carved from
walrus ivory. Each piece is a figural silhouette rather than a turned profile --
a seated king and queen, a mitred bishop, a horse-and-rider knight, a standing
warder (the rook) and a plain headstone pawn -- so they are hand-authored
outlines in the manner of :func:`chess2d.styles.staunton`'s knight.

Every figure is a single closed loop; the seated and standing figures share a
wide trapezoidal robe/base so they read as one solid, printable piece.
"""

from __future__ import annotations

from build123d import (
    BuildLine,
    BuildSketch,
    Line,
    Plane,
    Sketch,
    Spline,
    make_face,
    mirror,
)

from ..geometry import centered, scaled


def _figure(outline: list[tuple[float, float]], smooth: bool = True) -> Sketch:
    """A filled figure from an outline walked once around its boundary.

    ``smooth`` fits a spline through the points (rounded, organic ivory); a
    straight-edged figure passes ``False``.
    """
    with BuildSketch() as sk:
        with BuildLine():
            if smooth:
                Spline(outline)
                Line(outline[-1], outline[0])
            else:
                for start, end in zip(outline, outline[1:] + outline[:1], strict=True):
                    Line(start, end)
        make_face()
    return sk.sketch


def make_pawn(scale: float = 1.0) -> Sketch:
    """Pawn: a plain octagonal headstone -- the one abstract Lewis piece."""
    outline = [
        (5.0, 0.0),
        (5.0, 14.0),
        (3.5, 19.0),      # shoulders in
        (3.5, 22.0),
        (2.0, 24.5),      # rounded top
        (-2.0, 24.5),
        (-3.5, 22.0),
        (-3.5, 19.0),
        (-5.0, 14.0),
        (-5.0, 0.0),
    ]
    return scaled(centered(_figure(outline, smooth=False)), scale)


def make_rook(scale: float = 1.0) -> Sketch:
    """Rook: the warder -- a standing figure holding a shield, biting its rim."""
    # A helmeted foot-soldier: wide base, a body, and a domed helmeted head.
    outline = [
        (7.0, 0.0),
        (6.0, 12.0),      # robe tapering up
        (5.0, 20.0),      # shoulder
        (5.5, 25.0),      # raised shield edge on the right
        (4.0, 27.0),
        (2.6, 25.0),      # neck
        (3.0, 30.0),      # helmet side
        (2.2, 33.5),      # domed helmet
        (0.0, 34.6),
        (-2.2, 33.5),
        (-3.0, 30.0),
        (-2.6, 25.0),
        (-4.0, 27.0),
        (-5.5, 25.0),
        (-5.0, 20.0),
        (-6.0, 12.0),
        (-7.0, 0.0),
    ]
    return scaled(centered(_figure(outline)), scale)


def make_knight(scale: float = 1.0, facing: str = "left") -> Sketch:
    """Knight: a rider on a stout pony -- the horse's head and the rider above."""
    if facing not in ("left", "right"):
        raise ValueError(f"facing must be 'left' or 'right', got {facing!r}")
    # Pony body on the right, its head reaching left, the rider's head on top.
    outline = [
        (8.0, 0.0),
        (8.5, 12.0),       # horse haunch
        (7.0, 18.0),
        (7.5, 24.0),       # rider's back
        (6.0, 28.0),
        (6.6, 32.0),       # rider's head
        (4.6, 33.5),
        (3.0, 31.0),
        (2.0, 26.0),       # rider's front
        (0.0, 22.0),       # saddle dip
        (-3.0, 21.5),      # horse neck
        (-6.5, 20.0),
        (-9.5, 17.5),      # horse muzzle (left)
        (-9.0, 14.5),
        (-6.0, 13.5),      # jaw
        (-4.5, 10.0),
        (-5.0, 4.0),       # chest
        (-3.0, 0.0),
    ]
    horse = _figure(outline)
    if facing == "right":
        horse = mirror(horse, about=Plane.YZ)
    return scaled(centered(horse), scale)


def make_bishop(scale: float = 1.0) -> Sketch:
    """Bishop: a standing cleric in a tall pointed mitre, holding a crozier."""
    outline = [
        (6.5, 0.0),
        (5.5, 14.0),       # robe
        (4.5, 22.0),       # shoulders
        (3.0, 27.0),       # neck
        (3.4, 30.0),
        (2.4, 33.0),       # mitre flares
        (1.2, 37.0),
        (0.0, 40.0),       # mitre point
        (-1.2, 37.0),
        (-2.4, 33.0),
        (-3.4, 30.0),
        (-3.0, 27.0),
        (-4.5, 22.0),
        (-5.5, 14.0),
        (-6.5, 0.0),
    ]
    return scaled(centered(_figure(outline)), scale)


def make_queen(scale: float = 1.0) -> Sketch:
    """Queen: seated and slender, rising to a tall three-point crown.

    Narrower and taller-crowned than the king, so the two seated figures read
    apart even as flat silhouettes.
    """
    outline = [
        (6.4, 0.0),
        (6.4, 5.0),        # narrow throne base
        (4.8, 7.0),
        (4.4, 18.0),       # slim robed body
        (3.8, 26.0),       # shoulder
        (2.8, 29.0),       # long neck
        (3.2, 32.0),
        (2.6, 34.5),       # head
        (3.4, 37.5),       # crown -- outer point
        (1.3, 36.0),
        (0.0, 39.5),       # crown -- centre point
        (-1.3, 36.0),
        (-3.4, 37.5),
        (-2.6, 34.5),
        (-3.2, 32.0),
        (-2.8, 29.0),
        (-3.8, 26.0),
        (-4.4, 18.0),
        (-4.8, 7.0),
        (-6.4, 5.0),
        (-6.4, 0.0),
    ]
    return scaled(centered(_figure(outline)), scale)


def make_king(scale: float = 1.0) -> Sketch:
    """King: broad and square-shouldered on a wide throne, a low banded crown."""
    # Deliberately much wider than the queen, with a low flat crown rather than
    # tall points -- the two seated figures must not read as the same shape.
    outline = [
        (12.0, 0.0),
        (12.0, 8.0),       # wide throne base
        (10.0, 10.0),
        (9.5, 22.0),       # broad body
        (8.5, 30.0),       # square shoulders
        (6.0, 33.5),       # neck
        (6.2, 36.0),
        (5.4, 38.5),       # head
        (5.8, 42.0),       # low, wide crown band -- king is tallest but broad
        (2.9, 40.5),
        (0.0, 43.5),
        (-2.9, 40.5),
        (-5.8, 42.0),
        (-5.4, 38.5),
        (-6.2, 36.0),
        (-6.0, 33.5),
        (-8.5, 30.0),
        (-9.5, 22.0),
        (-10.0, 10.0),
        (-12.0, 8.0),
        (-12.0, 0.0),
    ]
    return scaled(centered(_figure(outline)), scale)
