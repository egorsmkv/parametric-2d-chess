"""Smoke tests for the Gradio configurator app.

Skipped when the optional ``app`` extra (gradio) is not installed.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

gradio_app = pytest.importorskip("chess2d.gradio_app")

MODE_LABELS = list(gradio_app._MODES.keys())
BOARD_LABELS = list(gradio_app._BOARD_CHOICES.keys())
FIGURE_LABELS = list(gradio_app._FIGURE_CHOICES.keys())
MEDIUM_BOARD = gradio_app._default(gradio_app._BOARD_CHOICES, "medium")
MEDIUM_FIGURE = gradio_app._default(gradio_app._FIGURE_CHOICES, "medium")
# material, filament diameter, price/kg, layer height, infill %
PRINT_ARGS = ("PLA", 1.75, 25.0, 0.2, 15)
STYLE_LABELS = list(gradio_app._STYLE_CHOICES.keys())
DEFAULT_STYLE = STYLE_LABELS[0]


@pytest.mark.parametrize("mode_label", MODE_LABELS)
def test_preview_renders_board_and_pieces(mode_label: str) -> None:
    html = gradio_app.build_preview(mode_label, DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3)
    assert "<svg" in html
    # Board plus one figure per piece type.
    assert html.count("<figure") == 6


@pytest.mark.parametrize("board_label", BOARD_LABELS)
def test_preview_honours_board_size_presets(board_label: str) -> None:
    html = gradio_app.build_preview(MODE_LABELS[0], DEFAULT_STYLE, board_label, MEDIUM_FIGURE, 2, 3)
    _, square_size = gradio_app._BOARD_CHOICES[board_label]
    # The spec strip reports the resulting board dimensions.
    assert f"{square_size * 8:.0f} × {square_size * 8:.0f} mm" in html
    assert f"<b>{square_size:.0f} mm</b>" in html


def test_preview_includes_board_coordinates() -> None:
    html = gradio_app.build_preview(
        MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3,
    )
    for file in "abcdefgh":
        assert f"<span>{file}</span>" in html
    for rank in range(1, 9):
        assert f"<span>{rank}</span>" in html


def test_preview_reports_piece_dimensions() -> None:
    html = gradio_app.build_preview(
        MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3,
    )
    # One "<width> × <height> mm" caption per piece, plus the board chip.
    assert html.count("mm</small>") == 6


@pytest.mark.parametrize("figure_label", FIGURE_LABELS)
def test_preview_honours_figure_size_presets(figure_label: str) -> None:
    html = gradio_app.build_preview(MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, figure_label, 2, 3)
    assert "<svg" in html


def test_build_files_produces_downloadable_zip() -> None:
    # Vector formats only keeps the test fast; solids are covered elsewhere.
    archive = Path(
        gradio_app.build_files(
            MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3, False, *PRINT_ARGS,
        ),
    )
    assert archive.exists() and archive.suffix == ".zip"
    # The filename records the chosen configuration.
    assert "board-medium" in archive.name and "figures-medium" in archive.name
    names = zipfile.ZipFile(archive).namelist()
    assert any(n.endswith("initial_position.svg") for n in names)
    assert any(n.endswith(".dxf") for n in names)


def test_zip_carries_the_printing_report() -> None:
    archive = Path(
        gradio_app.build_files(
            MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3, False, *PRINT_ARGS,
        ),
    )
    with zipfile.ZipFile(archive) as bundle:
        assert gradio_app.REPORT_FILENAME in bundle.namelist()
        assert bundle.read(gradio_app.REPORT_FILENAME).startswith(b"%PDF-")


def test_report_button_returns_a_pdf() -> None:
    path = Path(
        gradio_app.build_report(
            MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3, *PRINT_ARGS,
        ),
    )
    assert path.suffix == ".pdf"
    data = path.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 5_000
    # More than a cover page: the formulae and notes follow.
    assert data.count(b"/Type /Page") - data.count(b"/Type /Pages") >= 2


def test_report_reflects_the_chosen_material() -> None:
    # A denser material must not silently produce an identical document.
    common = (MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3)
    light = Path(gradio_app.build_report(*common, "ABS", 1.75, 25.0, 0.2, 15)).read_bytes()
    heavy = Path(gradio_app.build_report(*common, "PETG", 1.75, 25.0, 0.2, 15)).read_bytes()
    assert light != heavy


def test_print_settings_converts_the_infill_percentage() -> None:
    settings = gradio_app._print_settings("PLA", 1.75, 25.0, 0.2, 45)
    assert settings.infill == pytest.approx(0.45)
    assert settings.material == "PLA"


def test_preview_reuses_one_workspace() -> None:
    # Re-rendering must not leak a new temp directory per call: the session
    # workspace only ever holds the fixed set of scratch subdirectories.
    for label in MODE_LABELS:
        gradio_app.build_preview(label, DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3)
    subdirs = {p.name for p in gradio_app._workspace().iterdir()}
    assert "preview" in subdirs
    assert subdirs <= {"preview", "build", "zip", "report", "bambu"}


def test_demo_builds() -> None:
    assert gradio_app.build_demo() is not None


# printer, plate contents, mesh tolerance, slice?, machine, process, filament
BAMBU_ARGS = ("Bambu Lab P1S", "One of each piece (6)", 0.05, False, "", "", "")


def test_the_machine_menu_offers_the_printers_nozzle_variants() -> None:
    choices = gradio_app._machine_choices(gradio_app.PRINTERS["Bambu Lab P1S"])
    # Automatic first, so the default needs no knowledge of preset names.
    assert choices[0] == gradio_app.AUTO_PROFILE
    assert len(choices) > 1
    assert all("Bambu Lab P1S" in name for name in choices[1:])
    assert any(name.endswith("0.4 nozzle") for name in choices)


def test_the_automatic_entry_reads_as_unset() -> None:
    assert gradio_app._chosen(gradio_app.AUTO_PROFILE) == ""
    # A typed preset name or path still comes through, trimmed.
    assert gradio_app._chosen("  Bambu Lab P1S 0.6 nozzle ") == "Bambu Lab P1S 0.6 nozzle"
    assert gradio_app._chosen("/tmp/mine.json") == "/tmp/mine.json"  # noqa: S108


def test_changing_the_printer_repoints_the_machine_menu() -> None:
    machine, _ = gradio_app._profile_hints("Bambu Lab A1 mini")
    choices = machine["choices"] if isinstance(machine, dict) else machine.choices
    flat = [c[0] if isinstance(c, tuple) else c for c in choices]
    assert all("A1 mini" in name for name in flat[1:])
    assert not any("P1S" in name for name in flat)


def test_bambu_button_returns_a_3mf_and_a_verdict() -> None:
    path_text, status = gradio_app.build_bambu(
        MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3, *BAMBU_ARGS,
    )
    path = Path(path_text)
    assert path.suffix == ".3mf" and zipfile.is_zipfile(path)
    # The plate is described, and an unsliced file is not passed off as ready.
    assert "Bambu Lab P1S" in status
    assert "fits" in status
    assert ".gcode.3mf" not in status


def test_bambu_filename_records_the_plate_contents() -> None:
    path_text, _ = gradio_app.build_bambu(
        MODE_LABELS[0],
        DEFAULT_STYLE,
        MEDIUM_BOARD,
        MEDIUM_FIGURE,
        2,
        3,
        "Bambu Lab A1 mini",
        "Full set (32)",
        0.1,
        False,
        "",
        "",
        "",
    )
    assert Path(path_text).name.endswith("_full-plate.3mf")


def test_slicing_without_bambu_studio_still_returns_the_plain_plate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The Space (and most machines) have no Bambu Studio: the download must
    # still arrive, with the status saying plainly that it was not sliced.
    # Both ends have to be blinded: the app reads its own imported name for the
    # status line, while the slicer reads the one in its defining module.
    # Patching the chess2d.bambu re-export instead would rebind a name nobody
    # looks at, and this test would pass without ever exercising the fallback.
    monkeypatch.setattr(gradio_app, "find_bambu_studio", lambda _=None: None)
    monkeypatch.setattr("chess2d.bambu.slicing.find_bambu_studio", lambda _=None: None)
    path_text, status = gradio_app.build_bambu(
        MODE_LABELS[0],
        DEFAULT_STYLE,
        MEDIUM_BOARD,
        MEDIUM_FIGURE,
        2,
        3,
        "Bambu Lab P1S",
        "One of each piece (6)",
        0.1,
        True,
        "",
        "",
        "",
    )
    assert Path(path_text).suffix == ".3mf"
    assert "Not sliced" in status
    assert gradio_app._bambu_status().startswith("Bambu Studio was **not found**")
