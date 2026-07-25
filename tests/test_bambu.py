"""Tests for the Bambu Lab 3MF export and the Bambu Studio CLI wrapper.

Nothing here needs Bambu Studio installed: the slicing tests drive
:func:`find_bambu_studio` through a fake executable and assert on the command
that would be run.
"""

from __future__ import annotations

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
    export_plate_3mf,
    find_bambu_studio,
    make_plate,
    plate_parts,
    profiles_dir,
    resolve_profile,
    slice_with_bambu_studio,
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
        (profiles / kind / f"{name}.json").write_text("{}")
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


def test_the_slice_command_carries_the_profiles_and_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _fake_install(tmp_path)
    output = tmp_path / "plate.gcode.3mf"
    recorded: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command: list[str], **_: object) -> Result:
        recorded.append(command)
        # Stand in for the slicer: the wrapper checks the file was written.
        Path(command[command.index("--export-3mf") + 1]).write_text("sliced")
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
    assert settings.count(";") == 1 and settings.endswith("P1P.json")
    assert command[command.index("--load-filaments") + 1].endswith("Basic @BBL P1P.json")


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
