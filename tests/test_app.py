"""Smoke tests for the Gradio configurator app.

Skipped when the optional ``app`` extra (gradio) is not installed.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

gradio_app = pytest.importorskip("chess2d.gradio_app")

MODE_LABELS = list(gradio_app._MODES.keys())


@pytest.mark.parametrize("mode_label", MODE_LABELS)
def test_preview_renders_board_and_pieces(mode_label: str) -> None:
    html = gradio_app.build_preview(mode_label, 50, 2, 3)
    assert "<svg" in html
    # Board plus one figure per piece type.
    assert html.count("<figure") == 6


def test_build_files_produces_downloadable_zip() -> None:
    # Vector formats only keeps the test fast; solids are covered elsewhere.
    archive = Path(gradio_app.build_files(MODE_LABELS[0], 50, 2, 3, False))
    assert archive.exists() and archive.suffix == ".zip"
    names = zipfile.ZipFile(archive).namelist()
    assert any(n.endswith("initial_position.svg") for n in names)
    assert any(n.endswith(".dxf") for n in names)


def test_preview_reuses_one_workspace() -> None:
    # Re-rendering must not leak a new temp directory per call: the session
    # workspace only ever holds the fixed set of scratch subdirectories.
    for label in MODE_LABELS:
        gradio_app.build_preview(label, 50, 2, 3)
    subdirs = {p.name for p in gradio_app._workspace().iterdir()}
    assert "preview" in subdirs
    assert subdirs <= {"preview", "build", "zip"}


def test_demo_builds() -> None:
    assert gradio_app.build_demo() is not None
