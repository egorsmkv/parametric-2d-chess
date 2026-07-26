"""Bambu Lab output: 3MF print plates and, optionally, sliced ``.gcode.3mf``.

Two different targets live here, and they are not the same thing:

* A **generic 3MF** -- meshed geometry laid out on a build plate. It opens in
  Bambu Studio (or any slicer) but still has to be sliced there. Written purely
  with :class:`build123d.Mesher`, so it works anywhere the rest of the package
  works, including a Hugging Face Space. See :mod:`~chess2d.bambu.plate`.
* A **printer-ready 3MF** (``*.gcode.3mf``) -- the same plate run through the
  Bambu Studio command line against a machine/process/filament profile, so it
  arrives at the printer already sliced. This needs Bambu Studio installed on
  the machine running the app; without it :func:`find_bambu_studio` returns
  ``None`` and callers fall back to the generic file. See
  :mod:`~chess2d.bambu.slicing`.

The split runs along that line:

* :mod:`~chess2d.bambu.printers` -- the machine table and
  :class:`BambuStudioError`, shared by both halves and importing neither.
* :mod:`~chess2d.bambu.plate` -- packing and the generic 3MF. The only module
  here that imports build123d.
* :mod:`~chess2d.bambu.profiles` -- finding an installation and reading its
  system presets. Stdlib only.
* :mod:`~chess2d.bambu.slicing` -- the CLI wrapper and the slicer's own report.

Everything is re-exported here, so ``from chess2d.bambu import ...`` keeps
working regardless of which module a name ended up in. Note that monkeypatching
must still target the defining module (``chess2d.bambu.slicing.subprocess``,
not ``chess2d.bambu.subprocess``): rebinding a name here would not touch the
module global the callers actually read.
"""

from __future__ import annotations

from .plate import (
    DEFAULT_ANGULAR_TOLERANCE,
    DEFAULT_TOLERANCE,
    PLATE_CONTENTS,
    Placement,
    PlateContents,
    PlateLayout,
    arrange_plate,
    export_pieces_3mf,
    export_plate_3mf,
    make_plate,
    plate_parts,
)
from .printers import (
    DEFAULT_PRINTER,
    PART_GAP,
    PLATE_MARGIN,
    PRINTERS,
    BambuStudioError,
    Printer,
)
from .profiles import (
    EXECUTABLE_ENV,
    NOZZLE_SIZES,
    PROFILES_ENV,
    compatible_processes,
    default_filament,
    find_bambu_studio,
    flatten_profile,
    machine_profiles,
    profiles_dir,
    resolve_printer_profiles,
    resolve_process,
    resolve_profile,
    system_profiles,
)
from .slicing import (
    SliceReport,
    read_slice_report,
    slice_with_bambu_studio,
)

__all__ = [
    "DEFAULT_ANGULAR_TOLERANCE",
    "DEFAULT_PRINTER",
    "DEFAULT_TOLERANCE",
    "EXECUTABLE_ENV",
    "NOZZLE_SIZES",
    "PART_GAP",
    "PLATE_CONTENTS",
    "PLATE_MARGIN",
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
