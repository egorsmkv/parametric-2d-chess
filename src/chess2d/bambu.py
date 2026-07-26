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

import json
import os
import platform
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from build123d import Mesher, Part, Pos, Unit

from .estimate import piece_counts
from .parameters import SQUARE_SIZE, ChessStyle, FigureMode, PieceStyle, PieceType
from .pieces import make_piece_solid

__all__ = [
    "DEFAULT_PRINTER",
    "DEFAULT_TOLERANCE",
    "EXECUTABLE_ENV",
    "NOZZLE_SIZES",
    "PLATE_CONTENTS",
    "PRINTERS",
    "PROFILES_ENV",
    "BambuStudioError",
    "Placement",
    "PlateContents",
    "PlateLayout",
    "Printer",
    "SliceReport",
    "arrange_plate",
    "compatible_processes",
    "default_filament",
    "export_pieces_3mf",
    "export_plate_3mf",
    "find_bambu_studio",
    "flatten_profile",
    "machine_profiles",
    "make_plate",
    "plate_parts",
    "profiles_dir",
    "read_slice_report",
    "resolve_printer_profiles",
    "resolve_process",
    "resolve_profile",
    "slice_with_bambu_studio",
    "system_profiles",
]


# --------------------------------------------------------------------------
# Printers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Printer:
    """A Bambu machine: its usable plate and the system profiles that slice it.

    Both profile names are *starting points*, not gospel. Bambu renames presets
    between releases, and a process preset only slices for the machines listed
    in its own ``compatible_printers``; pairing the wrong two is what makes the
    CLI exit non-zero with "process not compatible with printer". When an
    installation is present, :func:`resolve_printer_profiles` checks these
    against its real profile tree and substitutes a compatible pair.
    """

    name: str
    #: Usable build-plate X/Y in millimetres.
    plate: tuple[float, float]
    #: Name of the Bambu Studio system machine profile (``--load-settings``).
    machine_profile: str
    #: Preferred process preset. Matched by prefix against the processes the
    #: installed tree says are compatible, so "0.20mm Standard" is enough.
    process_profile: str


#: Every Bambu machine the shipped profiles know about, in rough family order.
#: Plates and preset names are read off those profiles (the machine preset's own
#: ``printable_area`` and ``default_print_profile``), not from the marketing
#: pages -- and a test re-checks them against an installation. Note the P1S, X1
#: and X1E, which all slice with the *X1C's* process presets: nothing about the
#: model name would tell you that.
PRINTERS: dict[str, Printer] = {
    "Bambu Lab P1P": Printer(
        "Bambu Lab P1P",
        (256.0, 256.0),
        "Bambu Lab P1P 0.4 nozzle",
        "0.20mm Standard @BBL P1P",
    ),
    "Bambu Lab P1S": Printer(
        "Bambu Lab P1S",
        (256.0, 256.0),
        "Bambu Lab P1S 0.4 nozzle",
        "0.20mm Standard @BBL X1C",
    ),
    "Bambu Lab P2S": Printer(
        "Bambu Lab P2S",
        (256.0, 256.0),
        "Bambu Lab P2S 0.4 nozzle",
        "0.20mm Standard @BBL P2S",
    ),
    "Bambu Lab X1": Printer(
        "Bambu Lab X1",
        (256.0, 256.0),
        "Bambu Lab X1 0.4 nozzle",
        "0.20mm Standard @BBL X1C",
    ),
    "Bambu Lab X1 Carbon": Printer(
        "Bambu Lab X1 Carbon",
        (256.0, 256.0),
        "Bambu Lab X1 Carbon 0.4 nozzle",
        "0.20mm Standard @BBL X1C",
    ),
    "Bambu Lab X1E": Printer(
        "Bambu Lab X1E",
        (256.0, 256.0),
        "Bambu Lab X1E 0.4 nozzle",
        "0.20mm Standard @BBL X1C",
    ),
    "Bambu Lab X2D": Printer(
        "Bambu Lab X2D",
        (256.0, 256.0),
        "Bambu Lab X2D 0.4 nozzle",
        "0.20mm Standard @BBL X2D",
    ),
    "Bambu Lab A1 mini": Printer(
        "Bambu Lab A1 mini",
        (180.0, 180.0),
        "Bambu Lab A1 mini 0.4 nozzle",
        "0.20mm Standard @BBL A1M",
    ),
    "Bambu Lab A1": Printer(
        "Bambu Lab A1",
        (256.0, 256.0),
        "Bambu Lab A1 0.4 nozzle",
        "0.20mm Standard @BBL A1",
    ),
    "Bambu Lab A2L": Printer(
        "Bambu Lab A2L",
        (330.0, 320.0),
        "Bambu Lab A2L 0.4 nozzle",
        "0.20mm Standard @BBL A2L",
    ),
    "Bambu Lab H2C": Printer(
        "Bambu Lab H2C",
        (330.0, 320.0),
        "Bambu Lab H2C 0.4 nozzle",
        "0.20mm Standard @BBL H2C",
    ),
    "Bambu Lab H2S": Printer(
        "Bambu Lab H2S",
        (340.0, 320.0),
        "Bambu Lab H2S 0.4 nozzle",
        "0.20mm Standard @BBL H2S",
    ),
    "Bambu Lab H2D": Printer(
        "Bambu Lab H2D",
        (350.0, 320.0),
        "Bambu Lab H2D 0.4 nozzle",
        "0.20mm Standard @BBL H2D",
    ),
    "Bambu Lab H2D Pro": Printer(
        "Bambu Lab H2D Pro",
        (350.0, 320.0),
        "Bambu Lab H2D Pro 0.4 nozzle",
        "0.20mm Standard @BBL H2DP",
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


# --------------------------------------------------------------------------
# Bambu Studio CLI
# --------------------------------------------------------------------------


class BambuStudioError(RuntimeError):
    """Bambu Studio is missing, or its command line failed."""


#: Override the search with an explicit path when Bambu Studio is installed
#: somewhere unusual.
EXECUTABLE_ENV = "BAMBU_STUDIO"

#: Override the system-profile directory. Needed when the executable is a
#: wrapper script rather than the real binary -- an extracted AppImage in a
#: container, for instance, where the profiles are nowhere near ``$PATH``.
PROFILES_ENV = "BAMBU_PROFILES"

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


def profiles_dir(executable: str | Path | None = None) -> Path | None:
    """The bundled system-profile tree of an installation, if it can be found.

    Bambu Studio ships its machine/process/filament JSON under its resources
    directory; finding it lets callers name a profile instead of typing a path.
    ``$BAMBU_PROFILES`` wins outright, since no amount of guessing from the
    executable's path can find the profiles of an extracted AppImage behind a
    wrapper script.
    """
    if override := os.environ.get(PROFILES_ENV):
        path = Path(override).expanduser()
        return path if path.is_dir() else None

    # No executable given means "wherever Bambu Studio is". Without this the
    # callers that do not thread one through -- the app among them -- would
    # silently find no profiles and fall back to guesswork.
    if executable is None:
        executable = find_bambu_studio()
        if executable is None:
            return None

    executable = Path(executable).resolve()
    candidates = [
        # macOS: .../BambuStudio.app/Contents/MacOS/BambuStudio
        executable.parent.parent / "Resources" / "profiles",
        # Windows, and an extracted AppImage: alongside the executable.
        executable.parent / "resources" / "profiles",
        # AppImage layouts that put the binary one level down (bin/, usr/bin/).
        executable.parent.parent / "resources" / "profiles",
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

    root = profiles_dir(executable)
    if root is None:
        raise BambuStudioError(
            f"cannot resolve the {kind} profile {profile!r} by name: the Bambu Studio "
            "profile directory was not found. Pass a path to a .json profile instead.",
        )
    # Vendor trees are one directory per vendor; BBL is Bambu's own.
    for vendor in sorted(root.iterdir()):
        found = vendor / kind / f"{profile}.json"
        if found.is_file():
            return found
    raise BambuStudioError(f"no {kind} profile named {profile!r} under {root}")


# --------------------------------------------------------------------------
# Reading the installed profile tree
#
# Preset names and their pairings change between Bambu Studio releases, so
# anything hardcoded here rots. These helpers ask the installation instead.
# --------------------------------------------------------------------------


def system_profiles(kind: str, executable: str | Path | None = None) -> dict[str, Path]:
    """Every instantiable system preset of one ``kind``, by preset name.

    Base presets (``"instantiation": "false"``) are the halves of the
    inheritance chain a user can never select, so they are left out.
    """
    root = profiles_dir(executable)
    if root is None:
        return {}

    found: dict[str, Path] = {}
    for vendor in sorted(root.iterdir()):
        if not vendor.is_dir():
            continue
        for path in sorted((vendor / kind).glob("*.json")):
            data = _read_profile(path)
            if data is None or str(data.get("instantiation", "true")).lower() == "false":
                continue
            found[str(data.get("name", path.stem))] = path
    return found


def _read_profile(path: Path) -> dict[str, Any] | None:
    """Parse one preset, or ``None`` if it is unreadable.

    A single malformed file in a vendor tree we do not control must not take
    down profile discovery for everything else.
    """
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


#: Guards against a cyclic or absurdly deep ``inherits`` chain.
_MAX_INHERITANCE = 12


def _parent_profile(path: Path, parent: str) -> Path | None:
    """The file a preset's ``inherits`` refers to, if it can be located."""
    sibling = path.parent / f"{parent}.json"
    if sibling.is_file():
        return sibling
    # Some vendor trees file their base presets in a subdirectory.
    return next(path.parent.rglob(f"{parent}.json"), None)


def _profile_chain(path: Path) -> list[dict[str, Any]]:
    """A preset and its ancestors, root first, so a merge overrides correctly."""
    chain: list[dict[str, Any]] = []
    seen: set[Path] = set()
    current: Path | None = path

    while current is not None and current not in seen and len(chain) < _MAX_INHERITANCE:
        seen.add(current)
        data = _read_profile(current)
        if data is None:
            break
        chain.append(data)
        parent = data.get("inherits")
        current = _parent_profile(current, str(parent)) if parent else None

    return list(reversed(chain))


def flatten_profile(path: Path) -> dict[str, Any]:
    """One system preset merged with everything it inherits from.

    Bambu's system presets are fragments: a leaf like "0.20mm Standard @BBL P1P"
    carries only its own overrides and an ``inherits`` pointer. Handing such a
    fragment to ``--load-settings`` gives the slicer a config with most of its
    settings missing, which it reports as the preset being incompatible with the
    printer. Merging the chain first is what makes the CLI usable with the
    profiles that ship inside the installation.
    """
    merged: dict[str, Any] = {}
    for data in _profile_chain(path):
        merged.update(data)
    # The chain is already resolved; leaving the pointer in would send Bambu
    # Studio looking for a preset that was never loaded.
    merged.pop("inherits", None)
    return merged


def compatible_processes(machine: str, executable: str | Path | None = None) -> list[str]:
    """Process presets the installation says can slice for ``machine``.

    A preset that names no compatible printers at all is included: silence is
    not a refusal, and excluding it would leave callers with nothing to try.
    """
    matches: list[str] = []
    for name, path in system_profiles("process", executable).items():
        printers = flatten_profile(path).get("compatible_printers")
        if not printers or machine in printers:
            matches.append(name)
    return matches


def resolve_printer_profiles(
    printer: Printer,
    executable: str | Path | None = None,
    process_preference: str | None = None,
) -> tuple[str, str | None]:
    """Machine and process preset names that actually go together.

    Falls back to :class:`Printer`'s own guesses when no installation can be
    read -- there is then nothing to check them against, and letting Bambu
    Studio complain is better than refusing to try.
    """
    machines = system_profiles("machine", executable)
    if not machines:
        return printer.machine_profile, printer.process_profile

    machine = printer.machine_profile
    if machine not in machines:
        machine = _machine_for_model(printer.name, machines) or machine
    if machine not in machines:
        return printer.machine_profile, printer.process_profile

    return machine, resolve_process(
        machine, process_preference or printer.process_profile, executable,
    )


def resolve_process(
    machine: str,
    preference: str | None = None,
    executable: str | Path | None = None,
) -> str | None:
    """A process preset that can slice for ``machine``, honouring a preference.

    Always resolved against the machine actually in use, never against the
    printer model: the nozzle decides. A P1S with a 0.4 mm nozzle takes
    "0.20mm Standard @BBL X1C"; the same printer with a 0.6 mm nozzle rejects
    it and wants "0.30mm Standard @BBL X1C 0.6 nozzle".
    """
    processes = compatible_processes(machine, executable)
    if not processes:
        return None

    if preference:
        exact = [name for name in processes if name == preference]
        prefixed = [name for name in processes if name.startswith(preference)]
        if chosen := (exact or prefixed):
            return chosen[0]

    # Failing that, the machine preset names the process Bambu Studio itself
    # would select, which beats anything inferred from the model.
    machines = system_profiles("machine", executable)
    if machine in machines:
        default = flatten_profile(machines[machine]).get("default_print_profile")
        if isinstance(default, str) and default in processes:
            return default
    return processes[0]


def _machine_for_model(model: str, machines: dict[str, Path]) -> str | None:
    """The machine preset for a printer model, preferring the 0.4 mm nozzle.

    Matched on the preset's own ``printer_model`` field rather than on its name,
    which carries the nozzle size and varies in wording.
    """
    candidates = [
        name
        for name, path in machines.items()
        if flatten_profile(path).get("printer_model") == model
    ]
    if not candidates:
        return None
    return next((name for name in candidates if "0.4" in name), candidates[0])


#: Nozzles every Bambu machine preset comes in. Verified against an install:
#: each model ships exactly these four, named "<model> <nozzle> nozzle".
NOZZLE_SIZES: tuple[str, ...] = ("0.2", "0.4", "0.6", "0.8")


def machine_profiles(printer: Printer, executable: str | Path | None = None) -> list[str]:
    """The machine presets worth offering for one printer, nozzle order.

    Read from the installation when there is one. The fallback is generated
    from the same naming pattern rather than typed out, so it cannot disagree
    with itself -- but it is still only a guess, and the installed list wins.
    """
    machines = system_profiles("machine", executable)
    installed = sorted(
        (
            name
            for name, path in machines.items()
            if flatten_profile(path).get("printer_model") == printer.name
        ),
        key=_nozzle_of,
    )
    if installed:
        return installed
    return [f"{printer.name} {nozzle} nozzle" for nozzle in NOZZLE_SIZES]


def _nozzle_of(preset: str) -> float:
    """The nozzle size in a preset name, for ordering. Unknown sorts last."""
    parts = preset.split()
    for index, word in enumerate(parts):
        if word == "nozzle" and index:
            try:
                return float(parts[index - 1])
            except ValueError:
                break
    return float("inf")


def default_filament(machine: str, executable: str | Path | None = None) -> str | None:
    """The filament preset a machine ships with, if it names an installed one."""
    machines = system_profiles("machine", executable)
    if machine not in machines:
        return None
    declared = flatten_profile(machines[machine]).get("default_filament_profile")
    if isinstance(declared, list):
        declared = declared[0] if declared else None
    if not isinstance(declared, str):
        return None
    return declared if declared in system_profiles("filament", executable) else None


@dataclass(frozen=True)
class SliceReport:
    """What the slicer itself predicts for a plate, straight from its output.

    Exact for the machine and process it was sliced with, which is why the app
    prefers it over any estimate of ours: no model of print time competes with
    the slicer that generated the G-code.
    """

    #: Wall-clock print time in seconds, as Bambu Studio predicts it.
    seconds: float
    #: Filament mass in grams.
    grams: float
    #: Filament length in metres, when the plate records it.
    metres: float | None = None
    objects: int = 0

    def duration(self) -> str:
        """The print time as "1 h 25 min", or "48 min" under the hour."""
        total = round(self.seconds)
        hours, minutes = divmod(total // 60, 60)
        return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


def read_slice_report(sliced: str | Path) -> SliceReport | None:
    """Read the prediction Bambu Studio stored in a ``.gcode.3mf``.

    ``None`` when the file carries no slice metadata -- which is what an
    unsliced 3MF looks like, so this doubles as a check that slicing happened.
    """
    try:
        with zipfile.ZipFile(sliced) as bundle:
            raw = bundle.read("Metadata/slice_info.config")
    except (KeyError, OSError, zipfile.BadZipFile):
        return None

    try:
        # ``raw`` is slice metadata Bambu Studio itself wrote into a file this
        # process just produced, not third-party input.
        plate = ElementTree.fromstring(raw).find("plate")  # noqa: S314
    except ElementTree.ParseError:
        return None
    if plate is None:
        return None

    values = {item.get("key"): item.get("value") for item in plate.findall("metadata")}

    def number(key: str) -> float | None:
        try:
            return float(values[key])  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError):
            return None

    seconds, grams = number("prediction"), number("weight")
    if seconds is None or grams is None:
        return None

    metres = 0.0
    for filament in plate.findall("filament"):
        try:
            metres += float(filament.get("used_m", 0.0))
        except (TypeError, ValueError):
            continue

    return SliceReport(
        seconds=seconds,
        grams=grams,
        metres=metres or None,
        objects=len(plate.findall("object")),
    )


def _prepare_profile(profile: str | Path, kind: str, executable: str | Path, scratch: Path) -> Path:
    """The file to hand ``--load-settings`` for one preset.

    A path the caller supplied is passed through untouched -- a preset exported
    from Bambu Studio is already complete. A system preset named by the caller
    is flattened into ``scratch`` first, because the file in the installation is
    only a fragment (see :func:`flatten_profile`).
    """
    source = resolve_profile(profile, kind, executable)
    if Path(str(profile)).suffix == ".json" or Path(str(profile)).is_file():
        return source

    flattened = scratch / f"{kind}.json"
    flattened.write_text(json.dumps(flatten_profile(source)), encoding="utf-8")
    return flattened


def _check_pairing(
    machine: str | Path | None,
    process: str | Path | None,
    executable: str | Path,
) -> None:
    """Reject an incompatible machine/process pair before the CLI does.

    Bambu Studio's own answer to this is exit 239 and a log line reading
    "process not compatible with printer", which tells the user nothing about
    what would have worked. Only preset *names* can be checked -- a path points
    at a preset the user exported themselves, and its compatibility is theirs
    to judge.
    """
    if not machine or not process:
        return
    if Path(str(process)).suffix == ".json" or Path(str(machine)).suffix == ".json":
        return

    allowed = compatible_processes(str(machine), executable)
    if not allowed or str(process) in allowed:
        return
    shortlist = ", ".join(repr(name) for name in allowed[:5])
    raise BambuStudioError(
        f"the process profile {str(process)!r} does not list {str(machine)!r} among "
        f"its compatible printers, so Bambu Studio would refuse to slice it. "
        f"Compatible here: {shortlist}"
        + (f" (and {len(allowed) - 5} more)" if len(allowed) > 5 else ""),
    )


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
            "executable, to export a sliced .gcode.3mf.",
        )

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)

    _check_pairing(machine, process, binary)

    with tempfile.TemporaryDirectory(prefix="chess2d_profiles_") as scratch:
        settings = [
            str(_prepare_profile(value, kind, binary, Path(scratch)))
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
            command += [
                "--load-filaments",
                str(_prepare_profile(filament, "filament", binary, Path(scratch))),
            ]
        # --slice 0 slices every plate in the project.
        command += ["--slice", "0", "--export-3mf", str(out), str(model)]

        try:
            result = subprocess.run(  # noqa: S603 - argv is built here, never shell-interpolated
                command, capture_output=True, text=True, timeout=timeout, check=False,
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
            f"Bambu Studio exited with {result.returncode} and wrote no file.\n{tail}",
        )
    return out
