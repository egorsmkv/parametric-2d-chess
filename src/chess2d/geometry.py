"""Low-level geometry helpers shared by the piece and board builders.

These are pure functions: they take and return build123d geometry and never
touch the filesystem, the viewer or global state.
"""

from __future__ import annotations

from build123d import (
    Align,
    Circle,
    Plane,
    Pos,
    Rectangle,
    RectangleRounded,
    Rot,
    Sketch,
    mirror,
    scale,
)

# Two-sided figure border, in native mm (before fit-scaling). ``TWO_SIDED_BORDER``
# is the vertical gap between the two halves; a connecting neck of relative width
# ``TWO_SIDED_NECK_FRACTION`` bridges that gap so the whole figure stays a single
# connected, printable piece.
TWO_SIDED_BORDER: float = 2.5
TWO_SIDED_NECK_FRACTION: float = 0.45


def rounded_bar(
    width: float,
    height: float,
    y_bottom: float,
    radius: float | None = None,
) -> Sketch:
    """A horizontally centred rounded rectangle whose bottom edge sits at ``y_bottom``."""
    if radius is None:
        radius = min(width, height) * 0.22
    # RectangleRounded requires the radius to be smaller than half the
    # shortest side; clamp it so callers never trigger an invalid fillet.
    radius = max(0.0, min(radius, width / 2 - 0.01, height / 2 - 0.01))
    rect: Sketch = RectangleRounded(width, height, radius) if radius > 0 else (
        RectangleRounded(width, height, 0.01)
    )
    return Pos(0, y_bottom + height / 2) * rect


def disc(cx: float, cy: float, radius: float) -> Sketch:
    """A circle centred at ``(cx, cy)``."""
    return Pos(cx, cy) * Circle(radius)


def symmetric(half: Sketch) -> Sketch:
    """Union a right-hand half profile with its mirror image about the Y-axis.

    Any geometry that already straddles the Y-axis stays connected through the
    centre column, yielding a single symmetric face.
    """
    return half + mirror(half, about=Plane.YZ)


def two_sided(
    sketch: Sketch,
    border: float = TWO_SIDED_BORDER,
    neck_fraction: float = TWO_SIDED_NECK_FRACTION,
) -> Sketch:
    """Combine a centred piece with a 180-deg-rotated copy into a two-sided figure.

    The figure reads upright from *both* edges of the board, like a two-headed
    playing card: the top half faces the bottom player, and the bottom half is
    the same figure rotated 180 deg about Z (so the opposite player sees it
    upright and with correct left-right handedness -- essential for the knight).

    The two halves are separated by a ``border`` gap but joined through a central
    neck (of relative width ``neck_fraction``) that bridges the gap, so the whole
    figure stays a single connected piece -- printable / laser-cuttable as one
    element. The notches on either side of the neck read as the divider border.
    """
    box = sketch.bounding_box()
    shift = box.size.Y / 2 + border / 2
    top = Pos(0, shift) * sketch
    bottom = Rot(0, 0, 180) * top  # 180-deg rotation -> upright for the far player
    # Connecting neck bridging the border gap (overlaps 1 mm into each half).
    neck_width = max(box.size.X * neck_fraction, 2.0)
    neck = Rectangle(neck_width, border + 2.0)
    return top + bottom + neck


def centered(sketch: Sketch) -> Sketch:
    """Translate ``sketch`` so its bounding-box centre lands on the origin."""
    box = sketch.bounding_box()
    return Pos(-box.center().X, -box.center().Y) * sketch


def scaled(sketch: Sketch, factor: float) -> Sketch:
    """Uniformly scale a sketch, skipping the no-op case."""
    if factor == 1.0:
        return sketch
    return scale(sketch, by=factor)


def outline_wires(sketch: Sketch):
    """Return the boundary wires of a filled sketch as a manufacturing outline.

    This avoids the fragile inward-offset approach on silhouettes with sharp
    detail (spec 9.2): the outer/inner wires of the resolved face are always a
    set of valid closed loops suitable for plotting or CNC contouring.
    """
    wires = sketch.wires()
    return wires


def outline_ring(sketch: Sketch, width: float) -> Sketch | None:
    """Build a closed outline ring by subtracting an inward offset.

    Returns ``None`` when the offset is not robust for the given silhouette so
    callers can fall back to :func:`outline_wires`.
    """
    from build123d import offset

    try:
        inner = offset(sketch, amount=-width)
        ring = sketch - inner
    except Exception:  # noqa: BLE001 - offset can fail on sharp detail
        return None
    if ring is None or ring.area <= 0:
        return None
    return ring


# Re-export a couple of names so downstream modules can import align enums from
# here without pulling the whole build123d namespace.
CENTER = Align.CENTER
MIN = Align.MIN
MAX = Align.MAX
