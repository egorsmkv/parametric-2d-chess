"""Tests for the Bambu Studio CLI wrapper.

Covers :mod:`chess2d.bambu.slicing`. Nothing here needs Bambu Studio installed
except the one test under the "real installation" banner: the rest drive
:func:`find_bambu_studio` through a fixture tree and assert on the command that
would be run.

Note the monkeypatch targets. They name ``chess2d.bambu.slicing`` rather than
``chess2d.bambu``, because that is the module whose globals
:func:`slice_with_bambu_studio` actually reads -- patching the re-export on the
package would rebind a name nobody looks at, and the test would quietly stop
testing anything.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from chess2d.bambu import (
    PRINTERS,
    BambuStudioError,
    default_filament,
    export_plate_3mf,
    find_bambu_studio,
    resolve_printer_profiles,
    slice_with_bambu_studio,
)


class _Ok:
    """A successful :func:`subprocess.run` result."""

    returncode = 0
    stdout = ""
    stderr = ""


def test_slicing_without_bambu_studio_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("chess2d.bambu.slicing.find_bambu_studio", lambda _=None: None)
    with pytest.raises(BambuStudioError, match="not found"):
        slice_with_bambu_studio(tmp_path / "plate.3mf", tmp_path / "out.gcode.3mf")


def test_the_slicer_is_handed_a_complete_config_not_a_fragment(
    tmp_path: Path, install_with_profiles: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The regression this guards: passing the installation's own leaf JSON makes
    # Bambu Studio exit 239 with "process not compatible with printer", because
    # most of the config is in the presets it inherits from.
    handed: dict[str, dict[str, object]] = {}

    def fake_run(command: list[str], **_: object) -> _Ok:
        for path in command[command.index("--load-settings") + 1].split(";"):
            handed[Path(path).stem] = json.loads(Path(path).read_text(encoding="utf-8"))
        Path(command[command.index("--export-3mf") + 1]).write_text("sliced", encoding="utf-8")
        return _Ok()

    monkeypatch.setattr("chess2d.bambu.slicing.subprocess.run", fake_run)
    slice_with_bambu_studio(
        tmp_path / "plate.3mf",
        tmp_path / "out.gcode.3mf",
        machine="Bambu Lab P1S 0.4 nozzle",
        process="0.16mm Optimal @BBL P1P",
        executable=install_with_profiles,
    )

    assert handed["machine"]["printable_height"] == "250", "inherited setting missing"
    assert handed["machine"]["printer_model"] == "Bambu Lab P1S"
    # The process inherited its compatibility, which must reach the slicer.
    assert "Bambu Lab P1S 0.4 nozzle" in handed["process"]["compatible_printers"]


def test_an_incompatible_pair_is_refused_before_the_slicer_runs(
    tmp_path: Path, install_with_profiles: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_: object, **__: object) -> None:
        raise AssertionError("Bambu Studio must not be run with a rejected pair")

    monkeypatch.setattr("chess2d.bambu.slicing.subprocess.run", fail)
    with pytest.raises(BambuStudioError) as caught:
        slice_with_bambu_studio(
            tmp_path / "plate.3mf",
            tmp_path / "out.gcode.3mf",
            machine="Bambu Lab P1S 0.4 nozzle",
            process="0.20mm Standard @BBL A1M",
            executable=install_with_profiles,
        )
    # The message has to say what would work, not just what did not.
    assert "0.20mm Standard @BBL X1C" in str(caught.value)


def test_an_exported_profile_path_is_the_users_business(
    tmp_path: Path, install_with_profiles: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A .json path is a preset the user exported themselves; we cannot second
    # guess its compatibility, so the pairing check must stand aside.
    mine = tmp_path / "my_process.json"
    mine.write_text("{}", encoding="utf-8")
    ran: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> _Ok:
        ran.append(command)
        Path(command[command.index("--export-3mf") + 1]).write_text("sliced", encoding="utf-8")
        return _Ok()

    monkeypatch.setattr("chess2d.bambu.slicing.subprocess.run", fake_run)
    slice_with_bambu_studio(
        tmp_path / "plate.3mf",
        tmp_path / "out.gcode.3mf",
        machine="Bambu Lab P1S 0.4 nozzle",
        process=mine,
        executable=install_with_profiles,
    )
    assert ran, "the slice should have been attempted"


def test_the_slice_command_carries_the_profiles_and_output(
    tmp_path: Path, fake_install: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "plate.gcode.3mf"
    recorded: list[list[str]] = []
    presets: list[str] = []

    def fake_run(command: list[str], **_: object) -> _Ok:
        recorded.append(command)
        # The profiles are written to a scratch directory that is cleaned up on
        # the way out, so read them while the "slicer" is running.
        for flag in ("--load-settings", "--load-filaments"):
            for path in command[command.index(flag) + 1].split(";"):
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                presets.append(str(data.get("name", "")))
        # Stand in for the slicer: the wrapper checks the file was written.
        Path(command[command.index("--export-3mf") + 1]).write_text("sliced", encoding="utf-8")
        return _Ok()

    monkeypatch.setattr("chess2d.bambu.slicing.subprocess.run", fake_run)
    result = slice_with_bambu_studio(
        tmp_path / "plate.3mf",
        output,
        machine="Bambu Lab P1S 0.4 nozzle",
        process="0.20mm Standard @BBL P1P",
        filament="Bambu PLA Basic @BBL P1P",
        executable=fake_install,
    )

    assert result == output
    command = recorded[0]
    assert command[0] == str(fake_install)
    assert command[-1] == str(tmp_path / "plate.3mf")
    assert command[command.index("--export-3mf") + 1] == str(output)
    # Machine and process travel together in one --load-settings argument.
    settings = command[command.index("--load-settings") + 1]
    assert settings.count(";") == 1
    # The files are flattened copies, so identity is checked by preset name
    # rather than by filename.
    assert presets == [
        "Bambu Lab P1S 0.4 nozzle",
        "0.20mm Standard @BBL P1P",
        "Bambu PLA Basic @BBL P1P",
    ]


def test_a_failed_slice_reports_the_slicer_output(
    tmp_path: Path, fake_install: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Failed:
        returncode = 1
        stdout = "slicing failed: bed is too small"
        stderr = ""

    monkeypatch.setattr("chess2d.bambu.slicing.subprocess.run", lambda *_a, **_k: Failed())
    with pytest.raises(BambuStudioError, match="bed is too small"):
        slice_with_bambu_studio(
            tmp_path / "plate.3mf", tmp_path / "out.gcode.3mf", executable=fake_install,
        )


# --------------------------------------------------------------------------
# Against a real installation
#
# The only test that can prove the CLI wrapper works, so it is skipped in CI
# and on the Space.
# --------------------------------------------------------------------------

needs_bambu_studio = pytest.mark.skipif(
    find_bambu_studio() is None, reason="Bambu Studio is not installed",
)


@needs_bambu_studio
def test_a_plate_really_slices(tmp_path: Path) -> None:
    printer = PRINTERS["Bambu Lab P1S"]
    plate, _ = export_plate_3mf(tmp_path / "plate.3mf", printer=printer)
    machine, process = resolve_printer_profiles(printer)

    sliced = slice_with_bambu_studio(
        plate,
        tmp_path / "plate.gcode.3mf",
        machine=machine,
        process=process,
        filament=default_filament(machine),
        timeout=420,
    )

    # A .gcode.3mf that carries no G-code is just a renamed model file.
    with zipfile.ZipFile(sliced) as bundle:
        names = bundle.namelist()
        gcode = next(name for name in names if name.endswith(".gcode"))
        header = bundle.read(gcode)[:400].decode(errors="replace")
    assert "Metadata/slice_info.config" in names
    assert "total layer number" in header
