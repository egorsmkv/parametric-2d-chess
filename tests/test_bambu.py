"""Tests for the Bambu Lab 3MF export and the Bambu Studio CLI wrapper.

Nothing here needs Bambu Studio installed: the slicing tests drive
:func:`find_bambu_studio` through a fake executable and assert on the command
that would be run.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from chess2d.bambu import (
    PLATE_CONTENTS,
    PRINTERS,
    BambuStudioError,
    Placement,
    PlateContents,
    arrange_plate,
    compatible_processes,
    default_filament,
    export_plate_3mf,
    find_bambu_studio,
    flatten_profile,
    machine_profiles,
    make_plate,
    plate_parts,
    profiles_dir,
    resolve_printer_profiles,
    resolve_process,
    resolve_profile,
    slice_with_bambu_studio,
    system_profiles,
)
from chess2d.export import generate_all
from chess2d.parameters import ChessStyle, PieceType

P1S = PRINTERS["Bambu Lab P1S"]
A1_MINI = PRINTERS["Bambu Lab A1 mini"]


# --------------------------------------------------------------------------
# Plate contents
# --------------------------------------------------------------------------


def test_sample_plate_holds_one_of_each_piece() -> None:
    parts = plate_parts(PlateContents.SAMPLE)
    assert sorted(parts, key=list(PieceType).index) == list(PieceType)


def test_full_set_is_thirty_two_pieces() -> None:
    parts = plate_parts(PlateContents.FULL)
    assert len(parts) == 32
    assert parts.count(PieceType.PAWN) == 16
    assert parts.count(PieceType.KING) == 2


def test_one_side_is_half_a_set() -> None:
    side = plate_parts(PlateContents.SIDE)
    assert len(side) == 16
    assert side.count(PieceType.PAWN) == 8
    assert side.count(PieceType.KING) == 1


def test_every_menu_label_maps_to_a_real_selection() -> None:
    assert set(PLATE_CONTENTS.values()) == set(PlateContents)


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------


def _grid(count: int, width: float, height: float) -> list[tuple[PieceType, float, float]]:
    return [(PieceType.PAWN, width, height)] * count


def test_parts_stay_inside_the_plate_when_they_fit() -> None:
    layout = arrange_plate(_grid(12, 30.0, 30.0), P1S)
    assert layout.fits
    for placement in layout.placements:
        assert placement.x - placement.width / 2 >= 0
        assert placement.y - placement.height / 2 >= 0
        assert placement.x + placement.width / 2 <= P1S.plate[0]
        assert placement.y + placement.height / 2 <= P1S.plate[1]


def test_parts_do_not_overlap() -> None:
    layout = arrange_plate(_grid(30, 40.0, 25.0), P1S)

    def overlaps(a: Placement, b: Placement) -> bool:
        return (
            abs(a.x - b.x) < (a.width + b.width) / 2
            and abs(a.y - b.y) < (a.height + b.height) / 2
        )

    for i, first in enumerate(layout.placements):
        for second in layout.placements[i + 1:]:
            assert not overlaps(first, second)


def test_a_row_wraps_at_the_plate_edge() -> None:
    # Six 60 mm parts cannot share one 256 mm row, so they must wrap.
    layout = arrange_plate(_grid(6, 60.0, 20.0), P1S)
    assert len({placement.y for placement in layout.placements}) > 1


def test_overflow_is_reported_rather_than_dropped() -> None:
    layout = arrange_plate(_grid(60, 50.0, 50.0), A1_MINI)
    # Every part still gets a slot; the layout just admits it does not fit.
    assert layout.count == 60
    assert not layout.fits
    assert "does NOT fit" in layout.summary()


def test_a_full_set_fits_a_default_plate() -> None:
    _, layout = make_plate(ChessStyle(), PlateContents.FULL, P1S)
    assert layout.count == 32
    assert layout.fits


def test_solids_sit_on_the_plate_at_their_slots() -> None:
    parts, layout = make_plate(ChessStyle(), PlateContents.SAMPLE, P1S)
    assert len(parts) == len(layout.placements) == 6
    for part, placement in zip(parts, layout.placements, strict=True):
        box = part.bounding_box()
        # Bottom face on z = 0: the slicer must not have to drop it.
        assert abs(box.min.Z) < 1e-6
        assert abs(box.center().X - placement.x) < 1e-6
        assert abs(box.center().Y - placement.y) < 1e-6


# --------------------------------------------------------------------------
# 3MF file
# --------------------------------------------------------------------------


def test_3mf_is_a_valid_container_with_one_object_per_part(tmp_path: Path) -> None:
    path, layout = export_plate_3mf(tmp_path / "plate.3mf", ChessStyle())

    assert path.exists() and zipfile.is_zipfile(path)
    with zipfile.ZipFile(path) as container:
        assert "3D/3dmodel.model" in container.namelist()
        model = container.read("3D/3dmodel.model").decode()
    # One build item per placed part, named so the slicer's list is readable.
    assert model.count("<item ") == layout.count
    assert 'unit="millimeter"' in model
    for index, placement in enumerate(layout.placements, start=1):
        assert f'partnumber="{index:02d}-{placement.piece.value}"' in model


def test_3mf_geometry_is_millimetres_in_the_positive_quadrant(tmp_path: Path) -> None:
    import re

    style = ChessStyle(piece_thickness=2.0)
    path, _ = export_plate_3mf(tmp_path / "plate.3mf", style, PlateContents.SAMPLE)
    model = zipfile.ZipFile(path).read("3D/3dmodel.model").decode()
    vertices = [
        tuple(float(value) for value in match)
        for match in re.findall(
            r'<vertex x="([-\d.e+]+)" y="([-\d.e+]+)" z="([-\d.e+]+)"', model
        )
    ]
    assert vertices
    assert min(x for x, _, _ in vertices) >= 0
    assert min(y for _, y, _ in vertices) >= 0
    # Flat on the bed, exactly one piece thick.
    assert min(z for _, _, z in vertices) == pytest.approx(0.0, abs=1e-6)
    assert max(z for _, _, z in vertices) == pytest.approx(style.piece_thickness, abs=1e-6)


def _triangle_count(path: Path) -> int:
    return zipfile.ZipFile(path).read("3D/3dmodel.model").decode().count("<triangle")


def test_a_coarser_tolerance_makes_a_coarser_mesh(tmp_path: Path) -> None:
    # Only the extremes are compared: these pieces are flat, straight-sided
    # extrusions, so across the slider's own range the tolerance moves the
    # triangle count by a few percent in either direction.
    fine, _ = export_plate_3mf(tmp_path / "fine.3mf", tolerance=0.001)
    coarse, _ = export_plate_3mf(tmp_path / "coarse.3mf", tolerance=0.5)
    assert _triangle_count(coarse) < _triangle_count(fine)


def test_generate_all_can_include_the_3mf(tmp_path: Path) -> None:
    written = generate_all(tmp_path, with_solids=False, with_3mf=True)
    assert (tmp_path / "3mf" / "pieces.3mf").is_file()
    assert any(path.suffix == ".3mf" for path in written)


def test_generate_all_leaves_the_3mf_out_by_default(tmp_path: Path) -> None:
    generate_all(tmp_path, with_solids=False)
    assert not (tmp_path / "3mf").exists()


# --------------------------------------------------------------------------
# Bambu Studio discovery and CLI
# --------------------------------------------------------------------------


def test_an_explicit_path_wins_and_a_missing_one_is_not_invented(tmp_path: Path) -> None:
    fake = tmp_path / "BambuStudio"
    fake.write_text("")
    assert find_bambu_studio(fake) == fake
    assert find_bambu_studio(tmp_path / "nope") is None


def test_the_environment_variable_is_honoured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "BambuStudio"
    fake.write_text("")
    monkeypatch.setenv("BAMBU_STUDIO", str(fake))
    assert find_bambu_studio() == fake


def test_slicing_without_bambu_studio_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("chess2d.bambu.find_bambu_studio", lambda _=None: None)
    with pytest.raises(BambuStudioError, match="not found"):
        slice_with_bambu_studio(tmp_path / "plate.3mf", tmp_path / "out.gcode.3mf")


def _fake_install(tmp_path: Path) -> Path:
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
            json.dumps({"name": name, "type": kind}), encoding="utf-8"
        )
    return executable


def test_system_profiles_are_resolved_by_name(tmp_path: Path) -> None:
    executable = _fake_install(tmp_path)
    found = resolve_profile("Bambu Lab P1S 0.4 nozzle", "machine", executable)
    assert found.is_file() and found.name.endswith("0.4 nozzle.json")


def test_the_profile_directory_can_be_pointed_at_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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


def test_an_unknown_profile_name_is_an_error(tmp_path: Path) -> None:
    executable = _fake_install(tmp_path)
    with pytest.raises(BambuStudioError, match="no machine profile"):
        resolve_profile("Nonexistent Printer", "machine", executable)


# --------------------------------------------------------------------------
# Profile pairing
#
# The failure these guard against: Bambu Studio exits 239 with "process not
# compatible with printer" when a process preset is handed a machine that is
# not in its compatible_printers list.
# --------------------------------------------------------------------------


def _install_with_profiles(tmp_path: Path) -> Path:
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
            json.dumps({"name": name, **data}), encoding="utf-8"
        )

    # Machines inherit too: the leaf carries overrides, the base the bulk.
    write(
        "machine", "fdm_machine_bbl",
        {"type": "machine", "instantiation": "false",
         "printable_height": "250", "gcode_flavor": "marlin"},
    )
    write(
        "machine", "Bambu Lab P1S 0.4 nozzle",
        {"type": "machine", "inherits": "fdm_machine_bbl",
         "printer_model": "Bambu Lab P1S", "printer_variant": "0.4",
         "default_print_profile": "0.20mm Standard @BBL X1C",
         "default_filament_profile": ["Bambu PLA Basic @BBL P1S 0.4 nozzle"]},
    )
    # A second nozzle, which takes an entirely different set of processes.
    write(
        "machine", "Bambu Lab P1S 0.6 nozzle",
        {"type": "machine", "inherits": "fdm_machine_bbl",
         "printer_model": "Bambu Lab P1S", "printer_variant": "0.6",
         "default_print_profile": "0.30mm Standard @BBL X1C 0.6 nozzle"},
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
        "process", "0.30mm Standard @BBL X1C 0.6 nozzle",
        {"compatible_printers": ["Bambu Lab P1S 0.6 nozzle"]},
    )
    write(
        "process", "0.20mm Standard @BBL A1M",
        {"compatible_printers": ["Bambu Lab A1 mini 0.4 nozzle"]},
    )
    # Inherits its compatibility rather than declaring it.
    write("process", "base_process", {"compatible_printers": p1s, "instantiation": "false"})
    write("process", "0.16mm Optimal @BBL P1P", {"inherits": "base_process"})
    return executable


def test_a_preset_is_merged_with_what_it_inherits(tmp_path: Path) -> None:
    executable = _install_with_profiles(tmp_path)
    machine = system_profiles("machine", executable)["Bambu Lab P1S 0.4 nozzle"]
    flat = flatten_profile(machine)

    assert flat["printer_model"] == "Bambu Lab P1S", "the leaf's own settings survive"
    assert flat["printable_height"] == "250", "the base's settings come along"
    assert flat["name"] == "Bambu Lab P1S 0.4 nozzle", "the leaf keeps its identity"
    # Leaving the pointer in sends Bambu Studio after a preset it never loaded.
    assert "inherits" not in flat


def test_flattening_survives_a_cyclic_inherits(tmp_path: Path) -> None:
    _install_with_profiles(tmp_path)
    process = tmp_path / "BambuStudio.app" / "Contents" / "Resources"
    process = process / "profiles" / "BBL" / "process"
    (process / "loop_a.json").write_text(
        json.dumps({"name": "loop_a", "inherits": "loop_b"}), encoding="utf-8"
    )
    (process / "loop_b.json").write_text(
        json.dumps({"name": "loop_b", "inherits": "loop_a", "layer_height": "0.2"}),
        encoding="utf-8",
    )
    flat = flatten_profile(process / "loop_a.json")
    assert flat["name"] == "loop_a"
    assert flat["layer_height"] == "0.2"


def test_the_slicer_is_handed_a_complete_config_not_a_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The regression this guards: passing the installation's own leaf JSON makes
    # Bambu Studio exit 239 with "process not compatible with printer", because
    # most of the config is in the presets it inherits from.
    executable = _install_with_profiles(tmp_path)
    handed: dict[str, dict[str, object]] = {}

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command: list[str], **_: object) -> Result:
        for path in command[command.index("--load-settings") + 1].split(";"):
            handed[Path(path).stem] = json.loads(Path(path).read_text(encoding="utf-8"))
        Path(command[command.index("--export-3mf") + 1]).write_text(
            "sliced", encoding="utf-8"
        )
        return Result()

    monkeypatch.setattr("chess2d.bambu.subprocess.run", fake_run)
    slice_with_bambu_studio(
        tmp_path / "plate.3mf", tmp_path / "out.gcode.3mf",
        machine="Bambu Lab P1S 0.4 nozzle", process="0.16mm Optimal @BBL P1P",
        executable=executable,
    )

    assert handed["machine"]["printable_height"] == "250", "inherited setting missing"
    assert handed["machine"]["printer_model"] == "Bambu Lab P1S"
    # The process inherited its compatibility, which must reach the slicer.
    assert "Bambu Lab P1S 0.4 nozzle" in handed["process"]["compatible_printers"]


def test_the_machine_menu_lists_the_installed_nozzle_variants(tmp_path: Path) -> None:
    executable = _install_with_profiles(tmp_path)
    offered = machine_profiles(PRINTERS["Bambu Lab P1S"], executable)
    assert offered == ["Bambu Lab P1S 0.4 nozzle", "Bambu Lab P1S 0.6 nozzle"]
    # Another model's presets are not on this printer's menu.
    assert not any("A1 mini" in name for name in offered)


def test_the_machine_menu_falls_back_without_an_installation(tmp_path: Path) -> None:
    offered = machine_profiles(PRINTERS["Bambu Lab A1"], tmp_path / "nothing")
    assert offered == [
        "Bambu Lab A1 0.2 nozzle", "Bambu Lab A1 0.4 nozzle",
        "Bambu Lab A1 0.6 nozzle", "Bambu Lab A1 0.8 nozzle",
    ]


def test_the_process_follows_the_nozzle_not_the_model(tmp_path: Path) -> None:
    # Choosing a different nozzle changes which processes are legal: the 0.6 mm
    # presets reject the 0.4 mm process and vice versa.
    executable = _install_with_profiles(tmp_path)
    assert resolve_process("Bambu Lab P1S 0.4 nozzle", None, executable) == (
        "0.20mm Standard @BBL X1C"
    )
    assert resolve_process("Bambu Lab P1S 0.6 nozzle", None, executable) == (
        "0.30mm Standard @BBL X1C 0.6 nozzle"
    )


def test_an_incompatible_preference_does_not_survive_a_nozzle_change(
    tmp_path: Path,
) -> None:
    executable = _install_with_profiles(tmp_path)
    chosen = resolve_process(
        "Bambu Lab P1S 0.6 nozzle", "0.20mm Standard @BBL X1C", executable
    )
    assert chosen != "0.20mm Standard @BBL X1C"
    assert chosen in compatible_processes("Bambu Lab P1S 0.6 nozzle", executable)


def test_base_presets_are_not_offered(tmp_path: Path) -> None:
    executable = _install_with_profiles(tmp_path)
    machines = system_profiles("machine", executable)
    assert "Bambu Lab P1S 0.4 nozzle" in machines
    assert "fdm_machine_common" not in machines, "base presets are not selectable"


def test_only_processes_that_accept_the_machine_are_compatible(tmp_path: Path) -> None:
    executable = _install_with_profiles(tmp_path)
    found = compatible_processes("Bambu Lab P1S 0.4 nozzle", executable)
    assert "0.20mm Standard @BBL X1C" in found
    assert "0.20mm Standard @BBL A1M" not in found
    # Compatibility declared on a parent preset still counts.
    assert "0.16mm Optimal @BBL P1P" in found


def test_the_resolved_pair_is_one_the_slicer_accepts(tmp_path: Path) -> None:
    executable = _install_with_profiles(tmp_path)
    machine, process = resolve_printer_profiles(PRINTERS["Bambu Lab P1S"], executable)
    assert machine == "Bambu Lab P1S 0.4 nozzle"
    assert process in compatible_processes(machine, executable)


def test_a_process_preference_is_honoured_when_compatible(tmp_path: Path) -> None:
    executable = _install_with_profiles(tmp_path)
    _, process = resolve_printer_profiles(
        PRINTERS["Bambu Lab P1S"], executable, process_preference="0.08mm Extra Fine"
    )
    assert process == "0.08mm Extra Fine @BBL P1P"


def test_an_impossible_preference_falls_back_to_something_compatible(
    tmp_path: Path,
) -> None:
    executable = _install_with_profiles(tmp_path)
    machine, process = resolve_printer_profiles(
        PRINTERS["Bambu Lab P1S"], executable, process_preference="0.20mm Standard @BBL A1M"
    )
    # Never hand back the incompatible one just because it was asked for.
    assert process != "0.20mm Standard @BBL A1M"
    assert process in compatible_processes(machine, executable)


def test_without_an_installation_the_table_is_used_as_given(tmp_path: Path) -> None:
    printer = PRINTERS["Bambu Lab P1S"]
    machine, process = resolve_printer_profiles(printer, tmp_path / "nothing")
    assert (machine, process) == (printer.machine_profile, printer.process_profile)


def test_an_incompatible_pair_is_refused_before_the_slicer_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _install_with_profiles(tmp_path)

    def fail(*_: object, **__: object) -> None:
        raise AssertionError("Bambu Studio must not be run with a rejected pair")

    monkeypatch.setattr("chess2d.bambu.subprocess.run", fail)
    with pytest.raises(BambuStudioError) as caught:
        slice_with_bambu_studio(
            tmp_path / "plate.3mf", tmp_path / "out.gcode.3mf",
            machine="Bambu Lab P1S 0.4 nozzle",
            process="0.20mm Standard @BBL A1M",
            executable=executable,
        )
    # The message has to say what would work, not just what did not.
    assert "0.20mm Standard @BBL X1C" in str(caught.value)


def test_an_exported_profile_path_is_the_users_business(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A .json path is a preset the user exported themselves; we cannot second
    # guess its compatibility, so the pairing check must stand aside.
    executable = _install_with_profiles(tmp_path)
    mine = tmp_path / "my_process.json"
    mine.write_text("{}", encoding="utf-8")
    ran: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command: list[str], **_: object) -> Result:
        ran.append(command)
        Path(command[command.index("--export-3mf") + 1]).write_text(
            "sliced", encoding="utf-8"
        )
        return Result()

    monkeypatch.setattr("chess2d.bambu.subprocess.run", fake_run)
    slice_with_bambu_studio(
        tmp_path / "plate.3mf", tmp_path / "out.gcode.3mf",
        machine="Bambu Lab P1S 0.4 nozzle", process=mine, executable=executable,
    )
    assert ran, "the slice should have been attempted"


def test_the_slice_command_carries_the_profiles_and_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _fake_install(tmp_path)
    output = tmp_path / "plate.gcode.3mf"
    recorded: list[list[str]] = []
    presets: list[str] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command: list[str], **_: object) -> Result:
        recorded.append(command)
        # The profiles are written to a scratch directory that is cleaned up on
        # the way out, so read them while the "slicer" is running.
        for flag in ("--load-settings", "--load-filaments"):
            for path in command[command.index(flag) + 1].split(";"):
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                presets.append(str(data.get("name", "")))
        # Stand in for the slicer: the wrapper checks the file was written.
        Path(command[command.index("--export-3mf") + 1]).write_text(
            "sliced", encoding="utf-8"
        )
        return Result()

    monkeypatch.setattr("chess2d.bambu.subprocess.run", fake_run)
    result = slice_with_bambu_studio(
        tmp_path / "plate.3mf",
        output,
        machine="Bambu Lab P1S 0.4 nozzle",
        process="0.20mm Standard @BBL P1P",
        filament="Bambu PLA Basic @BBL P1P",
        executable=executable,
    )

    assert result == output
    command = recorded[0]
    assert command[0] == str(executable)
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


# --------------------------------------------------------------------------
# Against a real installation
#
# Everything above runs on fixtures. These run only where Bambu Studio is
# actually installed -- so they are skipped in CI and on the Space, and they
# are the only tests that can prove the CLI wrapper works.
# --------------------------------------------------------------------------

needs_bambu_studio = pytest.mark.skipif(
    find_bambu_studio() is None, reason="Bambu Studio is not installed"
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
    assert installed <= set(PRINTERS), (
        f"missing from PRINTERS: {sorted(installed - set(PRINTERS))}"
    )


@needs_bambu_studio
def test_a_plate_really_slices(tmp_path: Path) -> None:
    printer = PRINTERS["Bambu Lab P1S"]
    plate, _ = export_plate_3mf(tmp_path / "plate.3mf", printer=printer)
    machine, process = resolve_printer_profiles(printer)

    sliced = slice_with_bambu_studio(
        plate, tmp_path / "plate.gcode.3mf",
        machine=machine, process=process, filament=default_filament(machine),
        timeout=420,
    )

    # A .gcode.3mf that carries no G-code is just a renamed model file.
    with zipfile.ZipFile(sliced) as bundle:
        names = bundle.namelist()
        gcode = next(name for name in names if name.endswith(".gcode"))
        header = bundle.read(gcode)[:400].decode(errors="replace")
    assert "Metadata/slice_info.config" in names
    assert "total layer number" in header


def test_a_failed_slice_reports_the_slicer_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _fake_install(tmp_path)

    class Result:
        returncode = 1
        stdout = "slicing failed: bed is too small"
        stderr = ""

    monkeypatch.setattr("chess2d.bambu.subprocess.run", lambda *a, **k: Result())
    with pytest.raises(BambuStudioError, match="bed is too small"):
        slice_with_bambu_studio(
            tmp_path / "plate.3mf", tmp_path / "out.gcode.3mf", executable=executable
        )
