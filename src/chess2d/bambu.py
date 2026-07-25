"""Bambu Lab output: 3MF print plates and, optionally, sliced ``.gcode.3mf``.

Two different targets live here, and they are not the same thing:

* A **generic 3MF** -- meshed geometry laid out on a build plate. It opens in
  Bambu Studio (or any slicer) but still has to be sliced there. Written purely
  with :class:`build123d.Mesher`, so it works anywhere the rest of the package
  works, including a Hugging Face Space.
* A **printer-ready 3MF** (``*.gcode.3mf``) -- the same plate run through the
  Bambu Studio command line against a machine/process/filament profile, so it
  arrives at the printer already sliced. This needs Bambu Studio installed on
  the machine running the app; without it :func:`find_bambu_studio` returns
  ``None`` and callers fall back to the generic file.

The plate layout is a plain shelf packing: parts are placed left to right in
rows, tallest first. It is deliberately simple -- Bambu Studio's own
``--arrange`` does the real packing during slicing -- but it is enough to answer
the question the user actually has, which is "does one plate hold a whole set?".
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from build123d import Mesher, Part, Pos, Unit

from .estimate import piece_counts
from .parameters import SQUARE_SIZE, ChessStyle, FigureMode, PieceStyle, PieceType
from .pieces import make_piece_solid

__all__ = [
    "DEFAULT_PRINTER",
    "DEFAULT_TOLERANCE",
    "PLATE_CONTENTS",
    "PRINTERS",
    "BambuStudioError",
    "Placement",
    "PlateContents",
    "PlateLayout",
    "Printer",
    "arrange_plate",
    "export_pieces_3mf",
    "export_plate_3mf",
    "find_bambu_studio",
    "make_plate",
    "plate_parts",
    "profiles_dir",
    "resolve_profile",
    "slice_with_bambu_studio",
]


# --------------------------------------------------------------------------
# Printers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Printer:
    """A Bambu machine: its usable plate and the system profile that slices it."""

    name: str
    #: Usable build-plate X/Y in millimetres.
    plate: tuple[float, float]
    #: Name of the Bambu Studio system machine profile (``--load-settings``).
    machine_profile: str
    #: Matching system process profile, at the default 0.4 mm nozzle.
    process_profile: str


#: The plate figures are the printable areas Bambu publishes for each machine,
#: which are a few millimetres smaller than the sheet itself.
PRINTERS: dict[str, Printer] = {
    "Bambu Lab P1S": Printer(
        "Bambu Lab P1S", (256.0, 256.0),
        "Bambu Lab P1S 0.4 nozzle", "0.20mm Standard @BBL P1P",
    ),
    "Bambu Lab P1P": Printer(
        "Bambu Lab P1P", (256.0, 256.0),
        "Bambu Lab P1P 0.4 nozzle", "0.20mm Standard @BBL P1P",
    ),
    "Bambu Lab X1 Carbon": Printer(
        "Bambu Lab X1 Carbon", (256.0, 256.0),
        "Bambu Lab X1 Carbon 0.4 nozzle", "0.20mm Standard @BBL X1C",
    ),
    "Bambu Lab A1": Printer(
        "Bambu Lab A1", (256.0, 256.0),
        "Bambu Lab A1 0.4 nozzle", "0.20mm Standard @BBL A1",
    ),
    "Bambu Lab A1 mini": Printer(
        "Bambu Lab A1 mini", (180.0, 180.0),
        "Bambu Lab A1 mini 0.4 nozzle", "0.20mm Standard @BBL A1M",
    ),
    "Bambu Lab H2D": Printer(
        "Bambu Lab H2D", (325.0, 320.0),
        "Bambu Lab H2D 0.4 nozzle", "0.20mm Standard @BBL H2D",
    ),
}

DEFAULT_PRINTER = "Bambu Lab P1S"

#: Keep parts off the plate edge, where the first layer is least reliable.
PLATE_MARGIN = 6.0
#: Gap between neighbouring parts, wide enough to cut them apart by hand.
PART_GAP = 4.0


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
            )
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
    layout = arrange_plate(
        [(piece_type, *footprint[piece_type]) for piece_type in wanted], printer
    )

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
            * solid
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
    for index, (part, placement) in enumerate(
        zip(parts, layout.placements, strict=True), start=1
    ):
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
    """Write one of each piece to a 3MF, in the same signature style as the
    STEP/STL writers in :mod:`chess2d.export`."""
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


# --------------------------------------------------------------------------
# Bambu Studio CLI
# --------------------------------------------------------------------------


class BambuStudioError(RuntimeError):
    """Bambu Studio is missing, or its command line failed."""


#: Override the search with an explicit path when Bambu Studio is installed
#: somewhere unusual.
EXECUTABLE_ENV = "BAMBU_STUDIO"

_CANDIDATES: dict[str, tuple[str, ...]] = {
    "Darwin": ("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",),
    "Windows": (
        r"C:\Program Files\Bambu Studio\bambu-studio.exe",
        r"C:\Program Files\Bambu Studio\BambuStudio.exe",
    ),
    "Linux": (
        "/usr/bin/bambu-studio",
        "/usr/local/bin/bambu-studio",
        "/opt/bambu-studio/bambu-studio",
    ),
}


def find_bambu_studio(explicit: str | Path | None = None) -> Path | None:
    """Locate the Bambu Studio executable, or ``None`` if it is not installed.

    Checked in order: an explicit path, ``$BAMBU_STUDIO``, ``$PATH``, then the
    usual install location for this platform.
    """
    for candidate in (explicit, os.environ.get(EXECUTABLE_ENV)):
        if candidate:
            path = Path(candidate).expanduser()
            return path if path.exists() else None

    for name in ("bambu-studio", "BambuStudio", "bambustudio"):
        if found := shutil.which(name):
            return Path(found)

    for candidate in _CANDIDATES.get(platform.system(), ()):
        path = Path(candidate)
        if path.exists():
            return path
    return None


def profiles_dir(executable: str | Path) -> Path | None:
    """The bundled system-profile tree of an installation, if it can be found.

    Bambu Studio ships its machine/process/filament JSON under its resources
    directory; finding it lets callers name a profile instead of typing a path.
    """
    executable = Path(executable).resolve()
    candidates = [
        # macOS: .../BambuStudio.app/Contents/MacOS/BambuStudio
        executable.parent.parent / "Resources" / "profiles",
        # Windows: alongside the executable.
        executable.parent / "resources" / "profiles",
        # Linux packages: /usr/bin/bambu-studio -> /usr/share/...
        executable.parent.parent / "share" / "bambu-studio" / "profiles",
        executable.parent.parent / "share" / "BambuStudio" / "profiles",
    ]
    return next((path for path in candidates if path.is_dir()), None)


def resolve_profile(
    profile: str | Path,
    kind: str,
    executable: str | Path | None = None,
) -> Path:
    """Turn a profile name or path into an existing JSON file.

    ``kind`` is ``machine``, ``process`` or ``filament``. A path is used as
    given; a bare name (``"Bambu Lab P1S 0.4 nozzle"``) is looked up in the
    installation's own ``BBL`` profile tree.
    """
    direct = Path(profile).expanduser()
    if direct.suffix == ".json" or direct.is_file():
        if not direct.is_file():
            raise BambuStudioError(f"no such {kind} profile: {direct}")
        return direct

    root = profiles_dir(executable) if executable else None
    if root is None:
        raise BambuStudioError(
            f"cannot resolve the {kind} profile {profile!r} by name: the Bambu Studio "
            "profile directory was not found. Pass a path to a .json profile instead."
        )
    # Vendor trees are one directory per vendor; BBL is Bambu's own.
    for vendor in sorted(root.iterdir()):
        found = vendor / kind / f"{profile}.json"
        if found.is_file():
            return found
    raise BambuStudioError(f"no {kind} profile named {profile!r} under {root}")


def slice_with_bambu_studio(
    model: str | Path,
    output: str | Path,
    machine: str | Path | None = None,
    process: str | Path | None = None,
    filament: str | Path | None = None,
    executable: str | Path | None = None,
    arrange: bool = True,
    orient: bool = False,
    timeout: float = 600.0,
) -> Path:
    """Slice a 3MF into a printer-ready ``.gcode.3mf`` with the Bambu Studio CLI.

    ``machine``/``process``/``filament`` accept either a path to a JSON profile
    or the name of one of Bambu Studio's own system profiles. Raises
    :class:`BambuStudioError` if Bambu Studio is missing or the slice fails.

    The flat pieces here need no orientation, so ``orient`` defaults to off:
    they are already lying face-down on the plate, which is how they should
    print.
    """
    binary = find_bambu_studio(executable)
    if binary is None:
        raise BambuStudioError(
            "Bambu Studio was not found. Install it, or set $BAMBU_STUDIO to the "
            "executable, to export a sliced .gcode.3mf."
        )

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)

    settings = [
        str(resolve_profile(value, kind, binary))
        for value, kind in ((machine, "machine"), (process, "process"))
        if value
    ]

    command: list[str] = [str(binary)]
    if orient:
        command.append("--orient")
    if arrange:
        command += ["--arrange", "1"]
    if settings:
        command += ["--load-settings", ";".join(settings)]
    if filament:
        command += ["--load-filaments", str(resolve_profile(filament, "filament", binary))]
    # --slice 0 slices every plate in the project.
    command += ["--slice", "0", "--export-3mf", str(out), str(model)]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except OSError as error:  # pragma: no cover - depends on the local install
        raise BambuStudioError(f"could not run Bambu Studio: {error}") from error
    except subprocess.TimeoutExpired as error:  # pragma: no cover
        raise BambuStudioError(f"Bambu Studio timed out after {timeout:.0f}s") from error

    if result.returncode != 0 or not out.exists():
        # The CLI reports most failures on stdout, not stderr.
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = "\n".join(detail[-8:]) if detail else "no output"
        raise BambuStudioError(
            f"Bambu Studio exited with {result.returncode} and wrote no file.\n{tail}"
        )
    return out
