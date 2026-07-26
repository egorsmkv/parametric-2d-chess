"""Driving the Bambu Studio command line to produce a printer-ready 3MF.

A **printer-ready 3MF** (``*.gcode.3mf``) is a plate run through the Bambu
Studio command line against a machine/process/filament profile, so it arrives at
the printer already sliced. This needs Bambu Studio installed on the machine
running the app; without it :func:`~chess2d.bambu.profiles.find_bambu_studio`
returns ``None`` and callers fall back to the generic file from
:mod:`chess2d.bambu.plate`.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from .printers import BambuStudioError
from .profiles import compatible_processes, find_bambu_studio, flatten_profile, resolve_profile

__all__ = [
    "SliceReport",
    "read_slice_report",
    "slice_with_bambu_studio",
]


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
    only a fragment (see :func:`~chess2d.bambu.profiles.flatten_profile`).
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
    :class:`~chess2d.bambu.printers.BambuStudioError` if Bambu Studio is missing
    or the slice fails.

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
