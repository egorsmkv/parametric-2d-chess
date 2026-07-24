"""Material estimates for 3D-printing a generated chess set.

Pure arithmetic over exact geometry: the footprint area and perimeter come from
the same sketches the exporters write, so an estimate always describes the files
the user actually downloads.

Nothing here writes a file or imports a PDF library; :mod:`chess2d.report` turns
a :class:`SetEstimate` into a document.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from build123d import Sketch, extrude

from .assembly import BACK_RANK
from .board import make_board
from .parameters import ChessStyle, PieceType
from .pieces import make_piece

# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Material:
    """A printable material and the density used to turn volume into mass."""

    name: str
    density_g_cm3: float
    note: str


#: Densities are the usual published figures for filament/resin stock. Real
#: spools vary by a few percent between brands and colours.
MATERIALS: dict[str, Material] = {
    "PLA": Material("PLA", 1.24, "Easiest to print; stiff but brittle."),
    "PETG": Material("PETG", 1.27, "Tougher than PLA, slightly flexible."),
    "ABS": Material("ABS", 1.04, "Heat resistant; needs an enclosure."),
    "ASA": Material("ASA", 1.07, "Like ABS but UV stable."),
    "TPU": Material("TPU", 1.21, "Flexible; pieces would bend."),
    "Nylon (PA)": Material("Nylon (PA)", 1.14, "Very tough; absorbs moisture."),
    "Resin (SLA)": Material("Resin (SLA)", 1.10, "Finest detail; measured per litre."),
}

DEFAULT_MATERIAL = "PLA"

#: Slicers lay down this many fully solid layers at the top and bottom of a part.
SOLID_LAYERS = 8

#: Fraction of a print bed that is usable once parts are spaced apart.
BED_PACKING_EFFICIENCY = 0.7

#: A common bed, used for the "how many fit at once" figure.
DEFAULT_BED_MM: tuple[float, float] = (220.0, 220.0)

#: Suggested margin for purge, priming and the odd failed part.
WASTE_MARGIN = 0.05


@dataclass(frozen=True)
class PrintSettings:
    """Printer and material choices that scale the estimate."""

    material: str = DEFAULT_MATERIAL
    filament_diameter_mm: float = 1.75
    layer_height_mm: float = 0.2
    infill: float = 0.15
    wall_count: int = 2
    line_width_mm: float = 0.42
    price_per_kg: float = 25.0

    @property
    def density_g_cm3(self) -> float:
        return MATERIALS[self.material].density_g_cm3


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------


def wall_fraction(area_mm2: float, perimeter_mm: float, settings: PrintSettings) -> float:
    """How much of a cross-section the perimeter walls alone occupy.

    These silhouettes are narrow, so the walls are a large share of every layer
    (measured: 27-54% at the default two walls). Ignoring them would badly
    under-estimate a sparse-infill print.
    """
    if area_mm2 <= 0:
        return 1.0
    walls = perimeter_mm * settings.wall_count * settings.line_width_mm
    return min(1.0, walls / area_mm2)


def printed_fraction(
    area_mm2: float, perimeter_mm: float, thickness_mm: float, settings: PrintSettings
) -> float:
    """Share of the solid volume a sparse-infill print actually deposits.

    Solid top and bottom layers are laid whatever the infill setting is, so a
    thin part comes out effectively solid; only the layers between them are
    sparse, and there the walls still contribute.
    """
    if thickness_mm <= 0:
        return 1.0
    layers = max(1, math.ceil(thickness_mm / settings.layer_height_mm))
    solid = min(SOLID_LAYERS, layers)
    sparse = layers - solid
    if sparse <= 0:
        return 1.0
    walls = wall_fraction(area_mm2, perimeter_mm, settings)
    sparse_share = walls + (1.0 - walls) * settings.infill
    return (solid + sparse * sparse_share) / layers


def mass_g(volume_mm3: float, density_g_cm3: float) -> float:
    """Mass of a volume of material (mm^3 -> cm^3 -> grams)."""
    return volume_mm3 / 1000.0 * density_g_cm3


def filament_length_mm(volume_mm3: float, diameter_mm: float) -> float:
    """Length of round filament stock holding ``volume_mm3``."""
    cross_section = math.pi * (diameter_mm / 2.0) ** 2
    return volume_mm3 / cross_section if cross_section else 0.0


def cost(mass_grams: float, price_per_kg: float) -> float:
    return mass_grams / 1000.0 * price_per_kg


def pieces_per_bed(area_mm2: float, bed: tuple[float, float] = DEFAULT_BED_MM) -> int:
    """Roughly how many footprints fit on one bed, allowing for spacing."""
    if area_mm2 <= 0:
        return 0
    usable = bed[0] * bed[1] * BED_PACKING_EFFICIENCY
    return int(usable // area_mm2)


# --------------------------------------------------------------------------
# Per-part and whole-set estimates
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PartEstimate:
    """Geometry and volumes for one kind of part, and how many are needed."""

    name: str
    count: int
    area_mm2: float
    perimeter_mm: float
    thickness_mm: float

    @property
    def solid_volume_mm3(self) -> float:
        """Upper bound: the part printed fully dense."""
        return self.area_mm2 * self.thickness_mm

    def printed_volume_mm3(self, settings: PrintSettings) -> float:
        """Lower bound: what a sparse-infill print deposits."""
        return self.solid_volume_mm3 * printed_fraction(
            self.area_mm2, self.perimeter_mm, self.thickness_mm, settings
        )

    def total_solid_mm3(self) -> float:
        return self.solid_volume_mm3 * self.count

    def total_printed_mm3(self, settings: PrintSettings) -> float:
        return self.printed_volume_mm3(settings) * self.count


@dataclass(frozen=True)
class SetEstimate:
    """Everything the report needs about one configuration."""

    style: ChessStyle
    settings: PrintSettings
    pieces: list[PartEstimate]
    board: PartEstimate
    piece_counts: dict[PieceType, int] = field(default_factory=dict)

    # -- piece totals (the numbers most users care about) --

    @property
    def piece_count(self) -> int:
        return sum(part.count for part in self.pieces)

    @property
    def pieces_solid_mm3(self) -> float:
        return sum(part.total_solid_mm3() for part in self.pieces)

    @property
    def pieces_printed_mm3(self) -> float:
        return sum(part.total_printed_mm3(self.settings) for part in self.pieces)

    def mass_range_g(self) -> tuple[float, float]:
        density = self.settings.density_g_cm3
        return (
            mass_g(self.pieces_printed_mm3, density),
            mass_g(self.pieces_solid_mm3, density),
        )

    def filament_range_m(self) -> tuple[float, float]:
        diameter = self.settings.filament_diameter_mm
        return (
            filament_length_mm(self.pieces_printed_mm3, diameter) / 1000.0,
            filament_length_mm(self.pieces_solid_mm3, diameter) / 1000.0,
        )

    def cost_range(self) -> tuple[float, float]:
        low, high = self.mass_range_g()
        price = self.settings.price_per_kg
        return cost(low, price), cost(high, price)

    def budget_mass_g(self) -> float:
        """What to actually buy: the solid figure plus a waste margin."""
        return self.mass_range_g()[1] * (1.0 + WASTE_MARGIN)


def _perimeter(sketch: Sketch) -> float:
    """Total outline length of a silhouette, in mm."""
    return sum(edge.length for edge in sketch.edges())


def _footprint_area(sketch: Sketch, thickness: float) -> float:
    """True printed footprint of a silhouette, in mm^2.

    Derived from the extruded solid rather than ``Sketch.area``: where a
    composed figure overlaps itself the face area double-counts the overlap
    (the knight is 5% out), while the extrusion merges it -- and the extrusion
    is what the STL contains. Deriving the area back from the solid keeps
    ``V = A * t`` exactly true for every piece.
    """
    if thickness <= 0:
        return sketch.area
    return extrude(sketch, amount=thickness).volume / thickness


def piece_counts() -> dict[PieceType, int]:
    """How many of each piece a full set needs, both sides together.

    Derived from the real back rank rather than hardcoded, so it stays correct
    if the opening arrangement ever changes.
    """
    counts = Counter(BACK_RANK)
    counts[PieceType.PAWN] += 8
    return {piece: number * 2 for piece, number in counts.items()}


def estimate_set(
    style: ChessStyle | None = None,
    settings: PrintSettings | None = None,
) -> SetEstimate:
    """Measure a configuration and bundle everything the report needs."""
    style = style or ChessStyle()
    settings = settings or PrintSettings()
    counts = piece_counts()

    pieces: list[PartEstimate] = []
    for piece_type in PieceType:
        sketch = make_piece(
            piece_type,
            scale=style.piece_scale,
            mode=style.figure_mode,
            square_size=style.square_size,
        )
        pieces.append(
            PartEstimate(
                name=piece_type.value,
                count=counts[piece_type],
                area_mm2=_footprint_area(sketch, style.piece_thickness),
                perimeter_mm=_perimeter(sketch),
                thickness_mm=style.piece_thickness,
            )
        )

    # The board solid the exporter writes is the playing surface only (the
    # border is a 2D outline), so measure exactly that.
    board_geometry = make_board(
        square_size=style.square_size, border_width=style.border_width
    )
    # The squares tile edge to edge without overlapping, so the sketch area is
    # already exact here -- no need to extrude a large solid to check.
    squares = board_geometry.light_squares + board_geometry.dark_squares
    board = PartEstimate(
        name="board",
        count=1,
        area_mm2=squares.area,
        perimeter_mm=_perimeter(squares),
        thickness_mm=style.board_thickness,
    )

    return SetEstimate(
        style=style,
        settings=settings,
        pieces=pieces,
        board=board,
        piece_counts=counts,
    )
