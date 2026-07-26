"""Tests for locating Bambu Studio and reading its system profiles.

Covers :mod:`chess2d.bambu.profiles`. Everything below the "real installation"
banner runs against the fixture trees in ``conftest.py``; the tests under it are
skipped unless Bambu Studio is actually installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chess2d.bambu import (
    PRINTERS,
    BambuStudioError,
    compatible_processes,
    find_bambu_studio,
    flatten_profile,
    machine_profiles,
    profiles_dir,
    resolve_printer_profiles,
    resolve_process,
    resolve_profile,
    system_profiles,
)

# --------------------------------------------------------------------------
# Finding an installation
# --------------------------------------------------------------------------


def test_an_explicit_path_wins_and_a_missing_one_is_not_invented(tmp_path: Path) -> None:
    fake = tmp_path / "BambuStudio"
    fake.write_text("")
    assert find_bambu_studio(fake) == fake
    assert find_bambu_studio(tmp_path / "nope") is None


def test_the_environment_variable_is_honoured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "BambuStudio"
    fake.write_text("")
    monkeypatch.setenv("BAMBU_STUDIO", str(fake))
    assert find_bambu_studio() == fake


def test_system_profiles_are_resolved_by_name(fake_install: Path) -> None:
    found = resolve_profile("Bambu Lab P1S 0.4 nozzle", "machine", fake_install)
    assert found.is_file() and found.name.endswith("0.4 nozzle.json")


def test_the_profile_directory_can_be_pointed_at_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # How the container finds them: the executable is a wrapper script in
    # /usr/local/bin, so no amount of walking up from it reaches the profiles.
    executable = tmp_path / "wrapper" / "bambu-studio"
    executable.parent.mkdir()
    executable.write_text("")
    profiles = tmp_path / "elsewhere" / "BBL" / "machine"
    profiles.mkdir(parents=True)
    (profiles / "Bambu Lab P1S 0.4 nozzle.json").write_text("{}")

    assert profiles_dir(executable) is None
    monkeypatch.setenv("BAMBU_PROFILES", str(tmp_path / "elsewhere"))
    assert profiles_dir(executable) == tmp_path / "elsewhere"
    found = resolve_profile("Bambu Lab P1S 0.4 nozzle", "machine", executable)
    assert found.is_file()


def test_an_unknown_profile_name_is_an_error(fake_install: Path) -> None:
    with pytest.raises(BambuStudioError, match="no machine profile"):
        resolve_profile("Nonexistent Printer", "machine", fake_install)


# --------------------------------------------------------------------------
# Inheritance
# --------------------------------------------------------------------------


def test_a_preset_is_merged_with_what_it_inherits(install_with_profiles: Path) -> None:
    machine = system_profiles("machine", install_with_profiles)["Bambu Lab P1S 0.4 nozzle"]
    flat = flatten_profile(machine)

    assert flat["printer_model"] == "Bambu Lab P1S", "the leaf's own settings survive"
    assert flat["printable_height"] == "250", "the base's settings come along"
    assert flat["name"] == "Bambu Lab P1S 0.4 nozzle", "the leaf keeps its identity"
    # Leaving the pointer in sends Bambu Studio after a preset it never loaded.
    assert "inherits" not in flat


@pytest.mark.usefixtures("install_with_profiles")
def test_flattening_survives_a_cyclic_inherits(tmp_path: Path) -> None:
    # The fixture is here only for the tree it builds; the loop is added to it.
    process = tmp_path / "BambuStudio.app" / "Contents" / "Resources"
    process = process / "profiles" / "BBL" / "process"
    (process / "loop_a.json").write_text(
        json.dumps({"name": "loop_a", "inherits": "loop_b"}), encoding="utf-8",
    )
    (process / "loop_b.json").write_text(
        json.dumps({"name": "loop_b", "inherits": "loop_a", "layer_height": "0.2"}),
        encoding="utf-8",
    )
    flat = flatten_profile(process / "loop_a.json")
    assert flat["name"] == "loop_a"
    assert flat["layer_height"] == "0.2"


def test_base_presets_are_not_offered(install_with_profiles: Path) -> None:
    machines = system_profiles("machine", install_with_profiles)
    assert "Bambu Lab P1S 0.4 nozzle" in machines
    assert "fdm_machine_common" not in machines, "base presets are not selectable"


# --------------------------------------------------------------------------
# Profile pairing
#
# The failure these guard against: Bambu Studio exits 239 with "process not
# compatible with printer" when a process preset is handed a machine that is
# not in its compatible_printers list.
# --------------------------------------------------------------------------


def test_the_machine_menu_lists_the_installed_nozzle_variants(
    install_with_profiles: Path,
) -> None:
    offered = machine_profiles(PRINTERS["Bambu Lab P1S"], install_with_profiles)
    assert offered == ["Bambu Lab P1S 0.4 nozzle", "Bambu Lab P1S 0.6 nozzle"]
    # Another model's presets are not on this printer's menu.
    assert not any("A1 mini" in name for name in offered)


def test_the_machine_menu_falls_back_without_an_installation(tmp_path: Path) -> None:
    offered = machine_profiles(PRINTERS["Bambu Lab A1"], tmp_path / "nothing")
    assert offered == [
        "Bambu Lab A1 0.2 nozzle",
        "Bambu Lab A1 0.4 nozzle",
        "Bambu Lab A1 0.6 nozzle",
        "Bambu Lab A1 0.8 nozzle",
    ]


def test_the_process_follows_the_nozzle_not_the_model(install_with_profiles: Path) -> None:
    # Choosing a different nozzle changes which processes are legal: the 0.6 mm
    # presets reject the 0.4 mm process and vice versa.
    assert resolve_process("Bambu Lab P1S 0.4 nozzle", None, install_with_profiles) == (
        "0.20mm Standard @BBL X1C"
    )
    assert resolve_process("Bambu Lab P1S 0.6 nozzle", None, install_with_profiles) == (
        "0.30mm Standard @BBL X1C 0.6 nozzle"
    )


def test_an_incompatible_preference_does_not_survive_a_nozzle_change(
    install_with_profiles: Path,
) -> None:
    chosen = resolve_process(
        "Bambu Lab P1S 0.6 nozzle", "0.20mm Standard @BBL X1C", install_with_profiles,
    )
    assert chosen != "0.20mm Standard @BBL X1C"
    assert chosen in compatible_processes("Bambu Lab P1S 0.6 nozzle", install_with_profiles)


def test_only_processes_that_accept_the_machine_are_compatible(
    install_with_profiles: Path,
) -> None:
    found = compatible_processes("Bambu Lab P1S 0.4 nozzle", install_with_profiles)
    assert "0.20mm Standard @BBL X1C" in found
    assert "0.20mm Standard @BBL A1M" not in found
    # Compatibility declared on a parent preset still counts.
    assert "0.16mm Optimal @BBL P1P" in found


def test_the_resolved_pair_is_one_the_slicer_accepts(install_with_profiles: Path) -> None:
    machine, process = resolve_printer_profiles(
        PRINTERS["Bambu Lab P1S"], install_with_profiles,
    )
    assert machine == "Bambu Lab P1S 0.4 nozzle"
    assert process in compatible_processes(machine, install_with_profiles)


def test_a_process_preference_is_honoured_when_compatible(install_with_profiles: Path) -> None:
    _, process = resolve_printer_profiles(
        PRINTERS["Bambu Lab P1S"], install_with_profiles,
        process_preference="0.08mm Extra Fine",
    )
    assert process == "0.08mm Extra Fine @BBL P1P"


def test_an_impossible_preference_falls_back_to_something_compatible(
    install_with_profiles: Path,
) -> None:
    machine, process = resolve_printer_profiles(
        PRINTERS["Bambu Lab P1S"], install_with_profiles,
        process_preference="0.20mm Standard @BBL A1M",
    )
    # Never hand back the incompatible one just because it was asked for.
    assert process != "0.20mm Standard @BBL A1M"
    assert process in compatible_processes(machine, install_with_profiles)


def test_without_an_installation_the_table_is_used_as_given(tmp_path: Path) -> None:
    printer = PRINTERS["Bambu Lab P1S"]
    machine, process = resolve_printer_profiles(printer, tmp_path / "nothing")
    assert (machine, process) == (printer.machine_profile, printer.process_profile)


# --------------------------------------------------------------------------
# Against a real installation
#
# Everything above runs on fixtures. These run only where Bambu Studio is
# actually installed -- so they are skipped in CI and on the Space.
# --------------------------------------------------------------------------

needs_bambu_studio = pytest.mark.skipif(
    find_bambu_studio() is None, reason="Bambu Studio is not installed",
)


@needs_bambu_studio
def test_every_printer_resolves_to_a_pair_the_installation_accepts() -> None:
    # The bug this catches: a hardcoded process preset that the machine's own
    # compatible_printers list rejects, which the CLI reports as exit 239.
    for printer in PRINTERS.values():
        machine, process = resolve_printer_profiles(printer)
        assert machine in system_profiles("machine"), printer.name
        assert process in compatible_processes(machine), (
            f"{printer.name}: {process!r} cannot slice for {machine!r}"
        )


@needs_bambu_studio
def test_the_table_plates_match_the_installed_machine_presets() -> None:
    for printer in PRINTERS.values():
        settings = flatten_profile(system_profiles("machine")[printer.machine_profile])
        corners = [
            tuple(float(value) for value in corner.split("x"))
            for corner in settings["printable_area"]
        ]
        width = max(x for x, _ in corners)
        depth = max(y for _, y in corners)
        assert (width, depth) == printer.plate, f"{printer.name} plate is out of date"


@needs_bambu_studio
def test_the_menu_covers_every_bambu_model_the_installation_knows() -> None:
    # Skipped in CI, so this only speaks up on a machine where someone can act:
    # a new Bambu release adding a model should get an entry in PRINTERS.
    installed = {
        model
        for path in system_profiles("machine").values()
        if isinstance(model := flatten_profile(path).get("printer_model"), str)
        and model.startswith("Bambu Lab")
    }
    assert installed <= set(PRINTERS), f"missing from PRINTERS: {sorted(installed - set(PRINTERS))}"
