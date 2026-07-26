"""Finding a Bambu Studio installation and reading its system profiles.

Preset names and their pairings change between Bambu Studio releases, so
anything hardcoded rots. These helpers ask the installation instead: which
machine presets exist, which process presets will slice for a given machine,
and what a preset really contains once its inheritance chain is merged.

Stdlib only, and every entry point tolerates there being no installation at all
-- :func:`find_bambu_studio` returns ``None`` and the resolvers fall back to the
guesses in :data:`~chess2d.bambu.printers.PRINTERS`, so a Hugging Face Space can
import this module and simply offer the generic 3MF instead.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from .printers import BambuStudioError, Printer

__all__ = [
    "EXECUTABLE_ENV",
    "NOZZLE_SIZES",
    "PROFILES_ENV",
    "compatible_processes",
    "default_filament",
    "find_bambu_studio",
    "flatten_profile",
    "machine_profiles",
    "profiles_dir",
    "resolve_printer_profiles",
    "resolve_process",
    "resolve_profile",
    "system_profiles",
]


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


# --------------------------------------------------------------------------
# Pairing a machine with a process it can actually slice
# --------------------------------------------------------------------------


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

    Falls back to :class:`~chess2d.bambu.printers.Printer`'s own guesses when no
    installation can be read -- there is then nothing to check them against, and
    letting Bambu Studio complain is better than refusing to try.
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
