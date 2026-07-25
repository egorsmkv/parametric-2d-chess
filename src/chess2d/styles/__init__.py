"""The available piece styles and how each one composes onto its square.

Every style module exposes the same six ``make_*`` generators, so
:func:`chess2d.pieces.make_piece` can treat them interchangeably. A
:class:`StyleSpec` adds the per-style composition tuning that
:func:`chess2d.geometry.two_sided` and :func:`chess2d.geometry.fused_two_sided`
already accept as parameters.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from build123d import Sketch

from ..geometry import (
    FUSED_KEEP_FRACTION,
    TWO_SIDED_BORDER,
    TWO_SIDED_NECK_FRACTION,
)
from ..parameters import PieceStyle, PieceType
from . import (
    bauhaus,
    edinburgh,
    glyph,
    lewis,
    man_ray,
    regence,
    selenus,
    st_george,
    staunton,
)

Generator = Callable[..., Sketch]


@dataclass(frozen=True)
class StyleSpec:
    """One piece style: its generators, its labels and its composition tuning."""

    label: str
    note: str
    module: object
    #: Fraction of a piece kept when fusing. Turned styles carry their identity
    #: in the top third or so; geometric styles carry it in the whole outline and
    #: need a value near 1.0 or fusing reduces them all to similar blobs.
    fused_keep: float = FUSED_KEEP_FRACTION
    fused_overlap: float = 1.5
    two_sided_border: float = TWO_SIDED_BORDER
    neck_fraction: float = TWO_SIDED_NECK_FRACTION

    @property
    def generators(self) -> dict[PieceType, Generator]:
        return {
            piece_type: getattr(self.module, f"make_{piece_type.value}")
            for piece_type in PieceType
        }


STYLES: dict[PieceStyle, StyleSpec] = {
    PieceStyle.STAUNTON: StyleSpec(
        label="Staunton",
        note=(
            "The 1849 tournament standard: turned bodies with a flared foot, "
            "beaded collar and a distinctive top."
        ),
        module=staunton,
    ),
    PieceStyle.REGENCE: StyleSpec(
        label="Régence",
        note=(
            "Early 19th-century French: much taller and thinner, with long "
            "slender stems, stacked collar rings and small heads."
        ),
        module=regence,
        # Slimmer figures need a proportionally narrower connecting neck.
        neck_fraction=0.55,
    ),
    PieceStyle.SELENUS: StyleSpec(
        label="Selenus",
        note=(
            "The tiered German style: each piece is a stack of flat discs "
            "stepping inward, and you read the rank from the tiers and finial."
        ),
        module=selenus,
    ),
    PieceStyle.ST_GEORGE: StyleSpec(
        label="St. George",
        note=(
            "The pre-Staunton English standard: heavier and more bulbous, with "
            "pronounced collar rings and rounded ball finials."
        ),
        module=st_george,
    ),
    PieceStyle.EDINBURGH: StyleSpec(
        label="Edinburgh",
        note=(
            "The abstract 'North Upright' style: plain cylindrical columns "
            "stepped with sharp discs, the rank read from height and cap."
        ),
        module=edinburgh,
        neck_fraction=0.5,
    ),
    PieceStyle.BAUHAUS: StyleSpec(
        label="Bauhaus",
        note=(
            "After Hartwig, 1924: the shape states the move — square for the "
            "rook's straight lines, diamond for the bishop's diagonals, circle "
            "for the queen. Cuts and prints cleanly at any size."
        ),
        module=bauhaus,
        # Geometric pieces are identified by their whole outline, so keep it all.
        fused_keep=0.98,
        fused_overlap=0.6,
        two_sided_border=3.5,
        neck_fraction=0.32,
    ),
    PieceStyle.MAN_RAY: StyleSpec(
        label="Man Ray",
        note=(
            "After the artist's 1920s set: sphere, cube, cone, scrolled knight, "
            "coiled queen and stepped-pyramid king. Sculpture, not diagram."
        ),
        module=man_ray,
        # Whole-shape identity, like the other geometric style.
        fused_keep=0.98,
        fused_overlap=0.6,
        two_sided_border=3.5,
        neck_fraction=0.34,
    ),
    PieceStyle.LEWIS: StyleSpec(
        label="Isle of Lewis",
        note=(
            "After the 12th-century Norse carvings: squat figural pieces — a "
            "seated king and queen, a mitred bishop, a rider knight and a "
            "shield-biting warder."
        ),
        module=lewis,
        # Figural pieces read from their whole outline; keep most when fusing.
        fused_keep=0.9,
        neck_fraction=0.5,
    ),
    PieceStyle.GLYPH: StyleSpec(
        label="Diagram glyphs",
        note=(
            "The flat figurine symbols from printed chess diagrams: bold blocky "
            "icons on a wide skirt, built to stay legible when small."
        ),
        module=glyph,
        neck_fraction=0.4,
    ),
}

DEFAULT_STYLE: PieceStyle = PieceStyle.STAUNTON


def style_spec(style: PieceStyle) -> StyleSpec:
    """The :class:`StyleSpec` for a style."""
    return STYLES[style]


def generator_for(style: PieceStyle, piece_type: PieceType) -> Generator:
    """The generator drawing ``piece_type`` in ``style``."""
    return STYLES[style].generators[piece_type]


__all__ = [
    "DEFAULT_STYLE",
    "STYLES",
    "Generator",
    "StyleSpec",
    "generator_for",
    "style_spec",
]
