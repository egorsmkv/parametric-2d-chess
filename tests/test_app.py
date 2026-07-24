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
        MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3
    )
    for file in "abcdefgh":
        assert f"<span>{file}</span>" in html
    for rank in range(1, 9):
        assert f"<span>{rank}</span>" in html


def test_preview_reports_piece_dimensions() -> None:
    html = gradio_app.build_preview(
        MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3
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
            MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3, False, *PRINT_ARGS
        )
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
            MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3, False, *PRINT_ARGS
        )
    )
    with zipfile.ZipFile(archive) as bundle:
        assert gradio_app.REPORT_FILENAME in bundle.namelist()
        assert bundle.read(gradio_app.REPORT_FILENAME).startswith(b"%PDF-")


def test_report_button_returns_a_pdf() -> None:
    path = Path(
        gradio_app.build_report(
            MODE_LABELS[0], DEFAULT_STYLE, MEDIUM_BOARD, MEDIUM_FIGURE, 2, 3, *PRINT_ARGS
        )
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
    light = Path(gradio_app.build_report(
        *common, "ABS", 1.75, 25.0, 0.2, 15
    )).read_bytes()
    heavy = Path(gradio_app.build_report(
        *common, "PETG", 1.75, 25.0, 0.2, 15
    )).read_bytes()
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
    assert subdirs <= {"preview", "build", "zip", "report"}


def test_demo_builds() -> None:
    assert gradio_app.build_demo() is not None
