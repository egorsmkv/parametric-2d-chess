"""Print plates: what goes on one, where it sits, and the generic 3MF.

A **generic 3MF** is meshed geometry laid out on a build plate. It opens in
Bambu Studio (or any slicer) but still has to be sliced there. Written purely
with :class:`build123d.Mesher`, so it works anywhere the rest of the package
works, including a Hugging Face Space. Slicing it into a printer-ready file is
:mod:`chess2d.bambu.slicing`'s job, and needs Bambu Studio installed.

The plate layout is a plain shelf packing: parts are placed left to right in
rows, tallest first. It is deliberately simple -- Bambu Studio's own
``--arrange`` does the real packing during slicing -- but it is enough to answer
the question the user actually has, which is "does one plate hold a whole set?".

This is the only module in the package that imports build123d; everything to do
with a Bambu Studio installation is stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from build123d import Mesher, Part, Pos, Unit

from ..estimate import piece_counts
from ..parameters import SQUARE_SIZE, ChessStyle, FigureMode, PieceStyle, PieceType
from ..pieces import make_piece_solid
from .printers import DEFAULT_PRINTER, PART_GAP, PLATE_MARGIN, PRINTERS, Printer

__all__ = [
    "DEFAULT_ANGULAR_TOLERANCE",
    "DEFAULT_TOLERANCE",
    "PLATE_CONTENTS",
    "Placement",
    "PlateContents",
    "PlateLayout",
    "arrange_plate",
    "export_pieces_3mf",
    "export_plate_3mf",
    "make_plate",
    "plate_parts",
]


# --------------------------------------------------------------------------
# What goes on the plate
# --------------------------------------------------------------------------


class PlateContents(Enum):
    """How many pieces to lay out.

    Both players share one physical shape per piece type -- the figure modes are
    readable from either end of the board -- so a full set is simply every
    piece counted twice, printed in two filament colours.
    """

    SAMPLE = "sample"
    SIDE = "side"
    FULL = "full"


#: Human-readable labels for the UI, in menu order.
PLATE_CONTENTS: dict[str, PlateContents] = {
    "One of each piece (6)": PlateContents.SAMPLE,
    "One player's pieces (16)": PlateContents.SIDE,
    "Full set (32)": PlateContents.FULL,
}


def plate_parts(contents: PlateContents = PlateContents.SAMPLE) -> list[PieceType]:
    """Expand a plate selection into the individual parts to place.

    Counts come from :func:`chess2d.estimate.piece_counts`, which derives them
    from the real back rank, so the plate and the material report always agree.
    """
    if contents is PlateContents.SAMPLE:
        return list(PieceType)
    both_sides = piece_counts()
    divisor = 1 if contents is PlateContents.FULL else 2
    parts: list[PieceType] = []
    for piece_type in PieceType:
        parts.extend([piece_type] * (both_sides[piece_type] // divisor))
    return parts


# --------------------------------------------------------------------------
# Plate layout
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Placement:
    """One part on the plate, positioned by its centre."""

    piece: PieceType
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class PlateLayout:
    """The result of packing a set of parts onto one plate."""

    printer: Printer
    placements: list[Placement]
    #: Bounding size of everything placed, in millimetres.
    used: tuple[float, float]

    @property
    def count(self) -> int:
        return len(self.placements)

    @property
    def fits(self) -> bool:
        """Whether the whole selection sits inside the usable plate area."""
        width, height = self.used
        plate_x, plate_y = self.printer.plate
        return width <= plate_x - 2 * PLATE_MARGIN and height <= plate_y - 2 * PLATE_MARGIN

    def summary(self) -> str:
        """One line describing the packing, for the UI and the CLI."""
        width, height = self.used
        verdict = "fits" if self.fits else "does NOT fit"
        return (
            f"{self.count} parts, {width:.0f} × {height:.0f} mm — {verdict} on the "
            f"{self.printer.name} plate ({self.printer.plate[0]:.0f} × "
            f"{self.printer.plate[1]:.0f} mm)"
        )


def arrange_plate(
    sizes: list[tuple[PieceType, float, float]],
    printer: Printer,
    gap: float = PART_GAP,
) -> PlateLayout:
    """Shelf-pack parts into rows on ``printer``'s plate.

    Parts are placed tallest first, left to right, wrapping to a new row when
    the current one is full. Rows keep growing past the back of the plate if the
    selection is too big: the overflow is reported by :attr:`PlateLayout.fits`
    rather than silently dropped, so the caller can say so.
    """
    usable_x = printer.plate[0] - 2 * PLATE_MARGIN
    ordered = sorted(sizes, key=lambda item: item[2], reverse=True)

    placements: list[Placement] = []
    cursor_x = 0.0
    cursor_y = 0.0
    row_height = 0.0
    widest = 0.0

    for piece, width, height in ordered:
        # Wrap, unless the row is still empty (a single part wider than the
        # plate has nowhere better to go, and fits reports the truth).
        if cursor_x > 0 and cursor_x + width > usable_x:
            cursor_y += row_height + gap
            cursor_x = 0.0
            row_height = 0.0
        placements.append(
            Placement(
                piece=piece,
                x=PLATE_MARGIN + cursor_x + width / 2,
                y=PLATE_MARGIN + cursor_y + height / 2,
                width=width,
                height=height,
            ),
        )
        cursor_x += width + gap
        widest = max(widest, cursor_x - gap)
        row_height = max(row_height, height)

    return PlateLayout(
        printer=printer,
        placements=placements,
        used=(widest, cursor_y + row_height),
    )


def make_plate(
    style: ChessStyle | None = None,
    contents: PlateContents = PlateContents.SAMPLE,
    printer: Printer | None = None,
) -> tuple[list[Part], PlateLayout]:
    """Build the positioned solids for a print plate, plus their layout.

    Returns the parts as a list rather than one compound: the 3MF writer adds
    each as its own object, which is what lets Bambu Studio select, duplicate
    and re-arrange them individually.
    """
    style = style or ChessStyle()
    printer = printer or PRINTERS[DEFAULT_PRINTER]

    # One solid per piece type, reused for every copy of that piece.
    prototypes: dict[PieceType, Part] = {
        piece_type: make_piece_solid(
            piece_type,
            thickness=style.piece_thickness,
            scale=style.piece_scale,
            mode=style.figure_mode,
            square_size=style.square_size,
            style=style.piece_style,
        )
        for piece_type in PieceType
    }
    footprint = {
        piece_type: (solid.bounding_box().size.X, solid.bounding_box().size.Y)
        for piece_type, solid in prototypes.items()
    }

    wanted = plate_parts(contents)
    layout = arrange_plate([(piece_type, *footprint[piece_type]) for piece_type in wanted], printer)

    parts: list[Part] = []
    for placement in layout.placements:
        solid = prototypes[placement.piece]
        box = solid.bounding_box()
        # Move each copy from wherever it was authored to its slot, and drop it
        # onto z = 0 so the slicer sees it sitting on the plate.
        parts.append(
            Pos(
                placement.x - box.center().X,
                placement.y - box.center().Y,
                -box.min.Z,
            )
            * solid,
        )
    return parts, layout


# --------------------------------------------------------------------------
# 3MF
# --------------------------------------------------------------------------

#: Mesh tolerance in millimetres. 0.02 is plenty for FDM; drop to 0.01 for very
#: small pieces, raise to 0.05-0.1 for large simple ones.
DEFAULT_TOLERANCE = 0.02
DEFAULT_ANGULAR_TOLERANCE = 0.1


def export_plate_3mf(
    path: str | Path,
    style: ChessStyle | None = None,
    contents: PlateContents = PlateContents.SAMPLE,
    printer: Printer | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    angular_tolerance: float = DEFAULT_ANGULAR_TOLERANCE,
) -> tuple[Path, PlateLayout]:
    """Write a print plate as a generic 3MF. Returns the path and the layout."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    parts, layout = make_plate(style=style, contents=contents, printer=printer)

    mesher = Mesher(unit=Unit.MM)
    for index, (part, placement) in enumerate(zip(parts, layout.placements, strict=True), start=1):
        mesher.add_shape(
            part,
            linear_deflection=tolerance,
            angular_deflection=angular_tolerance,
            # Named parts so the slicer's object list is readable.
            part_number=f"{index:02d}-{placement.piece.value}",
        )
    mesher.write(str(out))
    return out, layout


def export_pieces_3mf(
    path: str | Path,
    thickness: float,
    scale: float = 1.0,
    mode: FigureMode = FigureMode.TWO_SIDED,
    square_size: float = SQUARE_SIZE,
    style: PieceStyle = PieceStyle.STAUNTON,
    tolerance: float = DEFAULT_TOLERANCE,
    angular_tolerance: float = DEFAULT_ANGULAR_TOLERANCE,
) -> Path:
    """Write one of each piece to a 3MF.

    Takes the same signature style as the STEP/STL writers in
    :mod:`chess2d.export`.
    """
    out, _ = export_plate_3mf(
        path,
        style=ChessStyle(
            square_size=square_size,
            piece_scale=scale,
            piece_thickness=thickness,
            figure_mode=mode,
            piece_style=style,
        ),
        contents=PlateContents.SAMPLE,
        tolerance=tolerance,
        angular_tolerance=angular_tolerance,
    )
    return out
