"""A Gradio app to configure the chess figures, preview the board and download files.

Launch with ``python -m chess2d.gradio_app`` or the ``chess2d-app`` console script
(install the extra first: ``uv sync --extra app``).
"""

from __future__ import annotations

import functools
import shutil
import tempfile
from pathlib import Path
from typing import Any

import gradio as gr

from .assembly import make_initial_position
from .export import export_composition_svg, export_piece_svg, generate_all
from .parameters import ChessStyle, FigureMode, PieceType

# Human-readable labels mapped to the underlying figure modes.
_MODES: dict[str, FigureMode] = {
    "Two-sided — both players (default)": FigureMode.TWO_SIDED,
    "Fused — compact, readable by everyone": FigureMode.FUSED,
    "Single-sided — classic (one orientation)": FigureMode.SINGLE,
}
_MODE_NOTES = {
    FigureMode.TWO_SIDED: (
        "Full figure plus its 180° rotation, stacked and joined by a border neck. "
        "Each player reads their own end; it looks tall on the board."
    ),
    FigureMode.FUSED: (
        "The identifying top of each piece merged with its 180° rotation into one "
        "compact, point-symmetric figure that reads the same from every side."
    ),
    FigureMode.SINGLE: (
        "A plain one-orientation silhouette — upright for the near player and "
        "upside-down for the opponent."
    ),
}


@functools.lru_cache(maxsize=1)
def _workspace() -> Path:
    """One reusable scratch directory for the whole session.

    Previews re-render on every control change, so a fresh ``mkdtemp`` per call
    would leak a directory each time; this reuses (and overwrites) one instead.
    """
    return Path(tempfile.mkdtemp(prefix="chess2d_app_"))


def _fresh_dir(name: str) -> Path:
    """An empty subdirectory of the session workspace."""
    path = _workspace() / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _style(mode_label: str, square_size: float, piece_thickness: float,
           board_thickness: float) -> ChessStyle:
    return ChessStyle(
        square_size=float(square_size),
        piece_thickness=float(piece_thickness),
        board_thickness=float(board_thickness),
        figure_mode=_MODES[mode_label],
    )


def _svg_inline(path: Path, max_width: int) -> str:
    """Read an exported SVG and make it scale responsively inside the page."""
    svg = path.read_text()
    # Drop the XML declaration and force the root <svg> to scale to its container.
    svg = svg.split("?>", 1)[-1]
    svg = svg.replace(
        "<svg ",
        f'<svg style="width:100%;height:auto;max-width:{max_width}px" ',
        1,
    )
    return svg


def build_preview(mode_label: str, square_size: float, piece_thickness: float,
                  board_thickness: float) -> str:
    """Render the board and the six piece silhouettes as inline SVG for preview."""
    style = _style(mode_label, square_size, piece_thickness, board_thickness)
    tmp = _fresh_dir("preview")

    composition = make_initial_position(style)
    board_svg = export_composition_svg(composition, tmp / "board.svg")

    cells = []
    for piece_type in PieceType:
        piece_svg = export_piece_svg(
            piece_type, tmp / f"{piece_type.value}.svg", style.piece_scale,
            mode=style.figure_mode,
        )
        cells.append(
            '<figure style="margin:0;text-align:center;background:#c9bd94;'
            'padding:6px;border-radius:6px">'
            f'<div style="height:120px;display:flex;align-items:center;'
            f'justify-content:center">{_svg_inline(piece_svg, 90)}</div>'
            f'<figcaption style="color:#222;font-size:12px;text-transform:capitalize">'
            f'{piece_type.value}</figcaption></figure>'
        )

    note = _MODE_NOTES[style.figure_mode]
    return (
        f'<div style="max-width:470px;margin:0 auto">{_svg_inline(board_svg, 470)}</div>'
        f'<p style="text-align:center;color:#666;margin:10px 0 4px;font-size:13px">'
        f'{note}</p>'
        '<div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center;'
        f'margin-top:8px">{"".join(cells)}</div>'
    )


def build_files(mode_label: str, square_size: float, piece_thickness: float,
                board_thickness: float, with_solids: bool) -> str:
    """Generate the full deliverable set and return a downloadable ZIP path."""
    style = _style(mode_label, square_size, piece_thickness, board_thickness)
    out_dir = _fresh_dir("build")
    generate_all(output_dir=out_dir, style=style, with_solids=bool(with_solids))

    mode_tag = style.figure_mode.value
    archive_base = _fresh_dir("zip") / f"chess2d_{mode_tag}"
    shutil.make_archive(str(archive_base), "zip", out_dir)
    return f"{archive_base}.zip"


def build_demo() -> gr.Blocks:
    """Assemble the Gradio Blocks UI."""
    with gr.Blocks(title="2D Chess Set Generator") as demo:
        gr.Markdown(
            "# ♟️ 2D Chess Set Generator\n"
            "Configure the chess-piece figures, preview the board, and download "
            "**SVG / DXF / STEP / STL** files generated with build123d."
        )
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Configure")
                mode = gr.Radio(
                    choices=list(_MODES.keys()),
                    value=next(iter(_MODES)),
                    label="Figure form",
                )
                square_size = gr.Slider(30, 70, value=50, step=1, label="Square size (mm)")
                piece_thickness = gr.Slider(
                    1, 6, value=2, step=0.5, label="Piece thickness (mm, for STEP/STL)"
                )
                board_thickness = gr.Slider(
                    1, 8, value=3, step=0.5, label="Board thickness (mm, for STEP)"
                )
                with_solids = gr.Checkbox(
                    value=True, label="Include 3D solids (STEP + STL) — slower"
                )
                generate_btn = gr.Button("Generate files (ZIP)", variant="primary")
                download = gr.File(label="Download SVG / DXF / STEP / STL (ZIP)")
            with gr.Column(scale=2):
                gr.Markdown("### Preview")
                preview = gr.HTML()

        # Typed as Any: the controls are different component classes whose common
        # base does not expose the .change event helper.
        inputs: list[Any] = [mode, square_size, piece_thickness, board_thickness]
        demo.load(build_preview, inputs=inputs, outputs=preview)
        for control in inputs:
            control.change(build_preview, inputs=inputs, outputs=preview)

        generate_btn.click(
            build_files,
            inputs=[*inputs, with_solids],
            outputs=download,
        )
    return demo


def main(**launch_kwargs: object) -> None:
    """Launch the app (Gradio 6 takes the theme at launch time)."""
    launch_kwargs.setdefault("theme", gr.themes.Soft())
    build_demo().launch(**launch_kwargs)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
