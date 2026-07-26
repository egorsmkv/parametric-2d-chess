"""The machine table and the package's error type.

This is the root of :mod:`chess2d.bambu`: it imports nothing from its siblings,
so both halves of the package -- the geometry that lays out a plate and the
code that talks to a Bambu Studio installation -- can depend on it without
depending on each other. :class:`BambuStudioError` lives here for the same
reason, since both halves raise it.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DEFAULT_PRINTER",
    "PART_GAP",
    "PLATE_MARGIN",
    "PRINTERS",
    "BambuStudioError",
    "Printer",
]


class BambuStudioError(RuntimeError):
    """Bambu Studio is missing, or its command line failed."""


@dataclass(frozen=True)
class Printer:
    """A Bambu machine: its usable plate and the system profiles that slice it.

    Both profile names are *starting points*, not gospel. Bambu renames presets
    between releases, and a process preset only slices for the machines listed
    in its own ``compatible_printers``; pairing the wrong two is what makes the
    CLI exit non-zero with "process not compatible with printer". When an
    installation is present, :func:`chess2d.bambu.profiles.resolve_printer_profiles`
    checks these against its real profile tree and substitutes a compatible pair.
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
