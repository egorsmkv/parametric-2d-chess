"""A Gradio app to configure the chess figures, preview the board and download files.

Launch with ``python -m chess2d.gradio_app`` or the ``chess2d-app`` console script
(install the extra first: ``uv sync --extra app``).
"""

from __future__ import annotations

import functools
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import gradio as gr

from .assembly import make_initial_position
from .estimate import DEFAULT_MATERIAL, MATERIALS, PrintSettings
from .export import export_composition_svg, export_piece_svg, generate_all
from .parameters import (
    BLACK_FILL_COLOR,
    BOARD_SIZE_PRESETS,
    FIGURE_SIZE_PRESETS,
    LIGHT_SQUARE_COLOR,
    ChessStyle,
    FigureMode,
    PieceType,
)
from .pieces import FIGURE_FILL_FRACTION
from .report import write_material_report

#: Name the report carries inside the generated archive.
REPORT_FILENAME = "3d_printing_estimate.pdf"

# Human-readable labels mapped to the underlying figure modes.
_MODES: dict[str, FigureMode] = {
    "Two-sided": FigureMode.TWO_SIDED,
    "Fused": FigureMode.FUSED,
    "Single-sided": FigureMode.SINGLE,
}
# Size presets. Labels stay terse -- the exact millimetres land in the preview's
# spec strip, where there is room for them.
_BOARD_CHOICES: dict[str, tuple[str, float]] = {
    f"{name.capitalize()} · {size:.0f} mm": (name, size)
    for name, size in BOARD_SIZE_PRESETS.items()
}
_FIGURE_CHOICES: dict[str, tuple[str, float]] = {
    f"{name.capitalize()} · {mult * FIGURE_FILL_FRACTION:.0%}": (name, mult)
    for name, mult in FIGURE_SIZE_PRESETS.items()
}


def _default(choices: dict[str, tuple[str, float]], name: str) -> str:
    """The label of a named preset (used to pick the initial selection)."""
    return next(label for label, (key, _) in choices.items() if key == name)


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


def _style(mode_label: str, board_label: str, figure_label: str,
           piece_thickness: float, board_thickness: float) -> ChessStyle:
    _, square_size = _BOARD_CHOICES[board_label]
    _, piece_scale = _FIGURE_CHOICES[figure_label]
    return ChessStyle(
        square_size=square_size,
        piece_scale=piece_scale,
        piece_thickness=float(piece_thickness),
        board_thickness=float(board_thickness),
        figure_mode=_MODES[mode_label],
    )


# Styling for the preview pane. Colours come from the active Gradio theme's own
# CSS variables, so the preview follows light/dark mode instead of fighting it.
_CSS = """
.c2 { --c2-ink: var(--body-text-color, #1f2937);
      --c2-dim: var(--body-text-color-subdued, #6b7280);
      --c2-line: var(--border-color-primary, #e5e7eb);
      --c2-card: var(--background-fill-secondary, #f9fafb);
      font-variant-numeric: tabular-nums; }

/* Board with rank/file coordinates around it. */
.c2-frame { display: grid; gap: .3rem; max-width: 540px; margin: 0 auto;
            grid-template-columns: 1.1rem minmax(0, 1fr);
            grid-template-rows: minmax(0, 1fr) 1.1rem; }
.c2-ranks { display: grid; grid-template-rows: repeat(8, 1fr); }
.c2-files { display: grid; grid-template-columns: repeat(8, 1fr); }
.c2-ranks span, .c2-files span { display: grid; place-items: center;
            font-size: .7rem; color: var(--c2-dim); }
.c2-board { border: 1px solid var(--c2-line); border-radius: 6px;
            overflow: hidden; line-height: 0; }
.c2-board svg { display: block; width: 100%; height: auto; }

/* Spec strip. */
.c2-specs { display: flex; flex-wrap: wrap; gap: .4rem; justify-content: center;
            margin: .85rem 0 .5rem; }
.c2-chip { display: flex; flex-direction: column; align-items: center;
           gap: .1rem; padding: .35rem .6rem; min-width: 5.5rem;
           border: 1px solid var(--c2-line); border-radius: 8px;
           background: var(--c2-card); }
.c2-chip span { font-size: .62rem; letter-spacing: .04em; text-transform: uppercase;
                color: var(--c2-dim); }
.c2-chip b { font-size: .82rem; color: var(--c2-ink); white-space: nowrap; }

.c2-note { max-width: 40rem; margin: 0 auto .9rem; text-align: center;
           font-size: .8rem; line-height: 1.45; color: var(--c2-dim); }

/* Piece thumbnails. */
.c2-pieces { display: grid; gap: .5rem;
             grid-template-columns: repeat(auto-fit, minmax(5.2rem, 1fr)); }
.c2-piece { margin: 0; padding: .5rem .3rem .4rem; text-align: center;
            border: 1px solid var(--c2-line); border-radius: 8px;
            background: var(--c2-card); }
/* Fixed board-cream backdrop: keeps the dark figures legible in either theme. */
.c2-art { height: 5.5rem; display: grid; place-items: center; border-radius: 5px;
          background: var(--c2-square); padding: .3rem; }
.c2-art svg { max-height: 100%; max-width: 78%; width: auto; height: auto; }
.c2-piece figcaption { margin-top: .35rem; font-size: .74rem;
            text-transform: capitalize; color: var(--c2-ink); }
.c2-piece small { display: block; font-size: .64rem; color: var(--c2-dim); }

/* First-load skeleton, so the pane is never blank while geometry builds. */
.c2-skeleton { max-width: 540px; margin: 0 auto; aspect-ratio: 1;
               border: 1px solid var(--c2-line); border-radius: 6px;
               display: grid; place-items: center; font-size: .8rem;
               color: var(--c2-dim);
               background: repeating-conic-gradient(
                   var(--c2-card) 0% 25%, transparent 0% 50%) 0 0 / 25% 25%; }
"""

_PLACEHOLDER = (
    '<div class="c2"><div class="c2-skeleton">Building the board…</div></div>'
)

_FILES = "abcdefgh"


def _print_settings(material: str, filament_diameter: float, price_per_kg: float,
                    layer_height: float, infill_percent: float) -> PrintSettings:
    """Bundle the printing controls (the estimate's counterpart to :func:`_style`)."""
    return PrintSettings(
        material=material,
        filament_diameter_mm=float(filament_diameter),
        layer_height_mm=float(layer_height),
        # The slider is a percentage; the model works in 0-1.
        infill=float(infill_percent) / 100.0,
        price_per_kg=float(price_per_kg),
    )


def _svg_inline(path: Path) -> str:
    """Read an exported SVG so it can be embedded and scaled by CSS."""
    svg = path.read_text()
    # Drop the XML declaration; sizing is handled by the stylesheet above.
    return svg.split("?>", 1)[-1]


def _svg_dims(path: Path) -> tuple[float, float]:
    """Millimetre width/height straight from the SVG header (no re-rendering)."""
    header = path.read_text(errors="ignore")[:400]

    def value(attribute: str) -> float:
        found = re.search(rf'\b{attribute}="([0-9.]+)mm"', header)
        return float(found.group(1)) if found else 0.0

    return value("width"), value("height")


def _chip(label: str, value: str) -> str:
    return f'<div class="c2-chip"><span>{label}</span><b>{value}</b></div>'


def _css_rgb(color: tuple[float, float, float]) -> str:
    """A 0-1 float colour from parameters.py as a CSS rgb() string."""
    red, green, blue = (round(channel * 255) for channel in color)
    return f"rgb({red},{green},{blue})"


def build_preview(mode_label: str, board_label: str, figure_label: str,
                  piece_thickness: float, board_thickness: float) -> str:
    """Render the board and the six piece silhouettes as inline SVG for preview."""
    style = _style(mode_label, board_label, figure_label, piece_thickness, board_thickness)
    tmp = _fresh_dir("preview")

    composition = make_initial_position(style)
    board_svg = export_composition_svg(composition, tmp / "board.svg")

    cells = []
    tallest = 0.0
    for piece_type in PieceType:
        piece_svg = export_piece_svg(
            piece_type, tmp / f"{piece_type.value}.svg", style.piece_scale,
            # Dark fill on the cream backdrop below: the white set's cream fill
            # would be nearly invisible on a light card.
            fill=BLACK_FILL_COLOR,
            mode=style.figure_mode, square_size=style.square_size,
        )
        width, height = _svg_dims(piece_svg)
        tallest = max(tallest, height)
        cells.append(
            '<figure class="c2-piece">'
            f'<div class="c2-art">{_svg_inline(piece_svg)}</div>'
            f"<figcaption>{piece_type.value}"
            f"<small>{width:.0f} × {height:.0f} mm</small>"
            "</figcaption></figure>"
        )

    # Coordinates: files a-h left to right, ranks 8-1 top to bottom (White at the
    # bottom), laid out on the same 8-track grid as the squares so they line up.
    ranks = "".join(f"<span>{rank}</span>" for rank in range(8, 0, -1))
    files = "".join(f"<span>{file}</span>" for file in _FILES)

    playing = style.square_size * 8
    specs = "".join((
        _chip("Board", f"{playing:.0f} × {playing:.0f} mm"),
        _chip("Square", f"{style.square_size:.0f} mm"),
        _chip("Figures", f"{style.piece_scale * FIGURE_FILL_FRACTION:.0%} of square"),
        _chip("Tallest", f"{tallest:.0f} mm"),
        _chip("Thickness", f"{style.piece_thickness:g} mm"),
    ))

    return (
        f'<div class="c2" style="--c2-square:{_css_rgb(LIGHT_SQUARE_COLOR)}">'
        '<div class="c2-frame">'
        f'<div class="c2-ranks">{ranks}</div>'
        f'<div class="c2-board">{_svg_inline(board_svg)}</div>'
        "<div></div>"
        f'<div class="c2-files">{files}</div>'
        "</div>"
        f'<div class="c2-specs">{specs}</div>'
        f'<p class="c2-note">{_MODE_NOTES[style.figure_mode]}</p>'
        f'<div class="c2-pieces">{"".join(cells)}</div>'
        "</div>"
    )


def _config_stem(style: ChessStyle, board_label: str, figure_label: str) -> str:
    """Filename stem describing the chosen configuration."""
    board_name, _ = _BOARD_CHOICES[board_label]
    figure_name, _ = _FIGURE_CHOICES[figure_label]
    return f"chess2d_{style.figure_mode.value}_board-{board_name}_figures-{figure_name}"


def build_report(mode_label: str, board_label: str, figure_label: str,
                 piece_thickness: float, board_thickness: float,
                 material: str, filament_diameter: float, price_per_kg: float,
                 layer_height: float, infill_percent: float) -> str:
    """Write just the 3D-printing material report and return its path.

    Needs no STEP/STL, so this returns in about a second.
    """
    style = _style(mode_label, board_label, figure_label, piece_thickness, board_thickness)
    settings = _print_settings(
        material, filament_diameter, price_per_kg, layer_height, infill_percent
    )
    stem = _config_stem(style, board_label, figure_label)
    path = _fresh_dir("report") / f"{stem}_printing-estimate.pdf"
    write_material_report(path, style=style, settings=settings)
    return str(path)


def build_files(mode_label: str, board_label: str, figure_label: str,
                piece_thickness: float, board_thickness: float,
                with_solids: bool,
                material: str, filament_diameter: float, price_per_kg: float,
                layer_height: float, infill_percent: float) -> str:
    """Generate the full deliverable set and return a downloadable ZIP path."""
    style = _style(mode_label, board_label, figure_label, piece_thickness, board_thickness)
    out_dir = _fresh_dir("build")
    generate_all(output_dir=out_dir, style=style, with_solids=bool(with_solids))

    # The printing estimate travels with the models it describes.
    settings = _print_settings(
        material, filament_diameter, price_per_kg, layer_height, infill_percent
    )
    write_material_report(out_dir / REPORT_FILENAME, style=style, settings=settings)

    archive_base = _fresh_dir("zip") / _config_stem(style, board_label, figure_label)
    shutil.make_archive(str(archive_base), "zip", out_dir)
    return f"{archive_base}.zip"


def build_demo() -> gr.Blocks:
    """Assemble the Gradio Blocks UI."""
    with gr.Blocks(title="2D Chess Set Generator") as demo:
        gr.Markdown(
            "# ♟️ 2D Chess Set Generator\n"
            "Parametric chessboard and flat piece silhouettes, generated with "
            "[build123d](https://build123d.readthedocs.io). Configure it, watch the "
            "board update, then download **SVG / DXF / STEP / STL**."
        )
        with gr.Row():
            with gr.Column(scale=2, min_width=280):
                with gr.Group():
                    mode = gr.Radio(
                        choices=list(_MODES.keys()),
                        value=next(iter(_MODES)),
                        label="Figure form",
                        info="How each figure is composed on the square.",
                    )
                with gr.Group():
                    board_size = gr.Radio(
                        choices=list(_BOARD_CHOICES.keys()),
                        value=_default(_BOARD_CHOICES, "medium"),
                        label="Board size",
                        info="Size of one square; the board is eight of them.",
                    )
                    figure_size = gr.Radio(
                        choices=list(_FIGURE_CHOICES.keys()),
                        value=_default(_FIGURE_CHOICES, "medium"),
                        label="Figure size",
                        info="How much of its square each piece fills.",
                    )
                with gr.Accordion("Material & output", open=False):
                    piece_thickness = gr.Slider(
                        1, 6, value=2, step=0.5, label="Piece thickness (mm)",
                        info="Extrusion depth for STEP and STL.",
                    )
                    board_thickness = gr.Slider(
                        1, 8, value=3, step=0.5, label="Board thickness (mm)",
                        info="Used for the board STEP solid.",
                    )
                    with_solids = gr.Checkbox(
                        value=True, label="Include 3D solids (STEP + STL)",
                        info="Slower — untick for a quick vector-only export.",
                    )
                with gr.Accordion("3D printing estimate", open=False):
                    gr.Markdown(
                        "<small>Drives the material report. These do not change the "
                        "board drawing.</small>"
                    )
                    material = gr.Dropdown(
                        choices=list(MATERIALS.keys()),
                        value=DEFAULT_MATERIAL,
                        label="Material",
                    )
                    filament_diameter = gr.Radio(
                        choices=[1.75, 2.85],
                        value=1.75,
                        label="Filament diameter (mm)",
                    )
                    price_per_kg = gr.Number(
                        value=25.0, minimum=0, label="Price per kg",
                        info="In your own currency; the report just multiplies.",
                    )
                    layer_height = gr.Slider(
                        0.08, 0.32, value=0.2, step=0.02, label="Layer height (mm)"
                    )
                    infill = gr.Slider(
                        0, 100, value=15, step=5, label="Infill (%)",
                        info="Barely matters for thin pieces — the report explains why.",
                    )
                    report_btn: Any = gr.Button("Material report (PDF)")
                    report_file = gr.File(label="Your report (PDF)", height=100)

                generate_btn: Any = gr.Button(
                    "Generate files (ZIP)", variant="primary", size="lg"
                )
                download = gr.File(label="Your download", height=120)
                gr.Markdown(
                    "<small>The archive holds `svg/`, `dxf/`, the printing estimate "
                    "PDF and, with solids enabled, `step/` + `stl/`.</small>"
                )
            with gr.Column(scale=3, min_width=360):
                preview = gr.HTML(value=_PLACEHOLDER, label="Preview")

        # Event listeners (.change, .click) are attached to component classes
        # dynamically by gradio, so static analysis cannot see them -- how much
        # it resolves varies between environments. Annotating the receivers as
        # Any keeps the type check stable everywhere.
        inputs: list[Any] = [
            mode, board_size, figure_size, piece_thickness, board_thickness
        ]
        demo.load(build_preview, inputs=inputs, outputs=preview)
        for control in inputs:
            control.change(build_preview, inputs=inputs, outputs=preview)

        # Printing controls stay out of `inputs`: they do not affect the drawing,
        # and wiring them to .change would re-render the board for nothing.
        print_inputs: list[Any] = [
            material, filament_diameter, price_per_kg, layer_height, infill
        ]
        report_btn.click(
            build_report,
            inputs=[*inputs, *print_inputs],
            outputs=report_file,
        )
        generate_btn.click(
            build_files,
            inputs=[*inputs, with_solids, *print_inputs],
            outputs=download,
        )
    return demo


def main(**launch_kwargs: object) -> None:
    """Launch the app (Gradio 6 takes the theme and CSS at launch time)."""
    launch_kwargs.setdefault("theme", gr.themes.Soft())
    launch_kwargs.setdefault("css", _CSS)
    build_demo().launch(**launch_kwargs)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
