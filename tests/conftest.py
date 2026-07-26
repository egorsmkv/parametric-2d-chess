"""Fake Bambu Studio installation trees, shared by the bambu tests.

Nothing in the suite needs Bambu Studio installed. These fixtures build the
directory shapes a real installation has, so profile discovery
(:mod:`chess2d.bambu.profiles`) and the CLI wrapper
(:mod:`chess2d.bambu.slicing`) can both be driven against a fixture instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_install(tmp_path: Path) -> Path:
    """A macOS-shaped installation tree with one system profile of each kind."""
    executable = tmp_path / "BambuStudio.app" / "Contents" / "MacOS" / "BambuStudio"
    executable.parent.mkdir(parents=True)
    executable.write_text("")
    profiles = tmp_path / "BambuStudio.app" / "Contents" / "Resources" / "profiles" / "BBL"
    for kind, name in (
        ("machine", "Bambu Lab P1S 0.4 nozzle"),
        ("process", "0.20mm Standard @BBL P1P"),
        ("filament", "Bambu PLA Basic @BBL P1P"),
    ):
        (profiles / kind).mkdir(parents=True, exist_ok=True)
        (profiles / kind / f"{name}.json").write_text(
            json.dumps({"name": name, "type": kind}), encoding="utf-8",
        )
    return executable


@pytest.fixture
def install_with_profiles(tmp_path: Path) -> Path:
    """An installation whose P1S process presets are named for the P1P.

    That is the real trap: the P1S slices with `@BBL P1P` process presets, so a
    name assembled from the printer's own model is wrong in a way that only the
    compatible_printers list reveals.
    """
    executable = tmp_path / "BambuStudio.app" / "Contents" / "MacOS" / "BambuStudio"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    bbl = tmp_path / "BambuStudio.app" / "Contents" / "Resources" / "profiles" / "BBL"

    def write(kind: str, name: str, data: dict[str, object]) -> None:
        (bbl / kind).mkdir(parents=True, exist_ok=True)
        (bbl / kind / f"{name}.json").write_text(
            json.dumps({"name": name, **data}), encoding="utf-8",
        )

    # Machines inherit too: the leaf carries overrides, the base the bulk.
    write(
        "machine",
        "fdm_machine_bbl",
        {
            "type": "machine",
            "instantiation": "false",
            "printable_height": "250",
            "gcode_flavor": "marlin",
        },
    )
    write(
        "machine",
        "Bambu Lab P1S 0.4 nozzle",
        {
            "type": "machine",
            "inherits": "fdm_machine_bbl",
            "printer_model": "Bambu Lab P1S",
            "printer_variant": "0.4",
            "default_print_profile": "0.20mm Standard @BBL X1C",
            "default_filament_profile": ["Bambu PLA Basic @BBL P1S 0.4 nozzle"],
        },
    )
    # A second nozzle, which takes an entirely different set of processes.
    write(
        "machine",
        "Bambu Lab P1S 0.6 nozzle",
        {
            "type": "machine",
            "inherits": "fdm_machine_bbl",
            "printer_model": "Bambu Lab P1S",
            "printer_variant": "0.6",
            "default_print_profile": "0.30mm Standard @BBL X1C 0.6 nozzle",
        },
    )
    write("filament", "Bambu PLA Basic @BBL P1S 0.4 nozzle", {"type": "filament"})
    write("machine", "Bambu Lab A1 mini 0.4 nozzle", {"type": "machine"})
    # A base preset the user can never pick.
    write("machine", "fdm_machine_common", {"type": "machine", "instantiation": "false"})

    # Named for the X1C but compatible with the P1S: the trap that started this.
    p1s = ["Bambu Lab P1S 0.4 nozzle", "Bambu Lab P1P 0.4 nozzle"]
    write("process", "0.20mm Standard @BBL X1C", {"compatible_printers": p1s})
    write("process", "0.08mm Extra Fine @BBL P1P", {"compatible_printers": p1s})
    write(
        "process",
        "0.30mm Standard @BBL X1C 0.6 nozzle",
        {"compatible_printers": ["Bambu Lab P1S 0.6 nozzle"]},
    )
    write(
        "process",
        "0.20mm Standard @BBL A1M",
        {"compatible_printers": ["Bambu Lab A1 mini 0.4 nozzle"]},
    )
    # Inherits its compatibility rather than declaring it.
    write("process", "base_process", {"compatible_printers": p1s, "instantiation": "false"})
    write("process", "0.16mm Optimal @BBL P1P", {"inherits": "base_process"})
    return executable
