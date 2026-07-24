"""File export: SVG and DXF for 2D geometry, STEP and STL for optional solids.

Every function is pure output: it takes geometry plus a path and writes a file.
No geometry is generated here beyond grouping already-built shapes.
"""

from __future__ import annotations

from pathlib import Path

from build123d import (
    Color,
    Compound,
    ExportDXF,
    ExportSVG,
    Pos,
    Sketch,
    export_step,
    export_stl,
    extrude,
)

from .assembly import ChessComposition, make_initial_position
from .board import BoardGeometry, make_board
from .parameters import (
    BLACK_FILL_COLOR,
    DARK_SQUARE_COLOR,
    LIGHT_SQUARE_COLOR,
    SQUARE_SIZE,
    WHITE_FILL_COLOR,
    ChessStyle,
    FigureMode,
    PieceType,
)
from .pieces import make_piece, make_piece_solid


def _color(rgb: tuple[float, float, float]) -> Color:
    return Color(*rgb)


def _ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------


def export_piece_svg(
    piece_type: PieceType,
    path: str | Path,
    scale: float = 1.0,
    fill: tuple[float, float, float] = WHITE_FILL_COLOR,
    mode: FigureMode = FigureMode.TWO_SIDED,
    square_size: float = SQUARE_SIZE,
) -> Path:
    """Write a single filled piece silhouette as an SVG."""
    out = _ensure_parent(path)
    sketch = make_piece(piece_type, scale=scale, mode=mode, square_size=square_size)
    exporter = ExportSVG(fit_to_stroke=True)
    exporter.add_layer("fill", fill_color=_color(fill), line_color=Color(0.15, 0.15, 0.15))
    exporter.add_shape(sketch, layer="fill")
    exporter.write(str(out))
    return out


def export_board_svg(board: BoardGeometry, path: str | Path) -> Path:
    """Write the board (light + dark squares, border) as a layered SVG."""
    out = _ensure_parent(path)
    exporter = ExportSVG(fit_to_stroke=True)
    exporter.add_layer(
        "light", fill_color=_color(LIGHT_SQUARE_COLOR), line_color=_color(DARK_SQUARE_COLOR)
    )
    exporter.add_layer(
        "dark", fill_color=_color(DARK_SQUARE_COLOR), line_color=_color(DARK_SQUARE_COLOR)
    )
    exporter.add_shape(board.light_squares, layer="light")
    exporter.add_shape(board.dark_squares, layer="dark")
    if board.border is not None:
        exporter.add_layer("border", fill_color=None, line_color=Color(0.2, 0.2, 0.2))
        exporter.add_shape(board.border, layer="border")
    exporter.write(str(out))
    return out


def export_composition_svg(composition: ChessComposition, path: str | Path) -> Path:
    """Write the full board + both piece layers as a single layered SVG."""
    out = _ensure_parent(path)
    exporter = ExportSVG(fit_to_stroke=True)
    exporter.add_layer(
        "light", fill_color=_color(LIGHT_SQUARE_COLOR), line_color=_color(DARK_SQUARE_COLOR)
    )
    exporter.add_layer(
        "dark", fill_color=_color(DARK_SQUARE_COLOR), line_color=_color(DARK_SQUARE_COLOR)
    )
    exporter.add_layer(
        "white_pieces", fill_color=_color(WHITE_FILL_COLOR), line_color=Color(0.2, 0.2, 0.2)
    )
    exporter.add_layer(
        "black_pieces", fill_color=_color(BLACK_FILL_COLOR), line_color=Color(0.1, 0.1, 0.1)
    )
    exporter.add_shape(composition.board.light_squares, layer="light")
    exporter.add_shape(composition.board.dark_squares, layer="dark")
    exporter.add_shape(composition.white_pieces, layer="white_pieces")
    exporter.add_shape(composition.black_pieces, layer="black_pieces")
    exporter.write(str(out))
    return out


# --------------------------------------------------------------------------
# DXF
# --------------------------------------------------------------------------


def export_dxf(shapes: dict[str, Sketch], path: str | Path) -> Path:
    """Write a set of named shape layers to a single DXF."""
    out = _ensure_parent(path)
    exporter = ExportDXF()
    for name, shape in shapes.items():
        exporter.add_layer(name)
        exporter.add_shape(shape, layer=name)
    exporter.write(str(out))
    return out


# --------------------------------------------------------------------------
# STEP / STL (optional solids)
# --------------------------------------------------------------------------


def export_piece_step(
    piece_type: PieceType,
    path: str | Path,
    thickness: float,
    scale: float = 1.0,
    mode: FigureMode = FigureMode.TWO_SIDED,
    square_size: float = SQUARE_SIZE,
) -> Path:
    out = _ensure_parent(path)
    solid = make_piece_solid(
        piece_type, thickness=thickness, scale=scale, mode=mode, square_size=square_size
    )
    export_step(solid, str(out))
    return out


def export_piece_stl(
    piece_type: PieceType,
    path: str | Path,
    thickness: float,
    scale: float = 1.0,
    mode: FigureMode = FigureMode.TWO_SIDED,
    square_size: float = SQUARE_SIZE,
) -> Path:
    out = _ensure_parent(path)
    solid = make_piece_solid(
        piece_type, thickness=thickness, scale=scale, mode=mode, square_size=square_size
    )
    export_stl(solid, str(out))
    return out


def export_flat_pieces_step(
    path: str | Path,
    thickness: float,
    scale: float = 1.0,
    mode: FigureMode = FigureMode.TWO_SIDED,
    square_size: float = SQUARE_SIZE,
) -> Path:
    """All six flat-piece solids laid out in a row, as one STEP file."""
    out = _ensure_parent(path)
    solids = []
    for i, pt in enumerate(PieceType):
        solid = make_piece_solid(
            pt, thickness=thickness, scale=scale, mode=mode, square_size=square_size
        )
        solids.append(Pos((i - 2.5) * square_size * 0.95, 0, 0) * solid)
    compound = Compound(children=solids)
    export_step(compound, str(out))
    return out


# --------------------------------------------------------------------------
# Batch driver
# --------------------------------------------------------------------------


def generate_all(
    output_dir: str | Path = "output",
    style: ChessStyle | None = None,
    with_solids: bool = True,
) -> list[Path]:
    """Regenerate every deliverable under ``output_dir``. Returns written paths."""
    if style is None:
        style = ChessStyle()
    root = Path(output_dir)
    written: list[Path] = []

    board = make_board(square_size=style.square_size, border_width=style.border_width)
    composition = make_initial_position(style)

    # --- SVG ---
    svg_dir = root / "svg"
    written.append(export_board_svg(board, svg_dir / "board.svg"))
    for pt in PieceType:
        written.append(export_piece_svg(
            pt, svg_dir / f"{pt.value}.svg", style.piece_scale,
            mode=style.figure_mode, square_size=style.square_size))
    written.append(export_composition_svg(composition, svg_dir / "initial_position.svg"))

    # --- DXF ---
    dxf_dir = root / "dxf"
    written.append(export_dxf({"board": board.light_squares + board.dark_squares},
                              dxf_dir / "board.dxf"))
    # Space the pieces out so they do not overlap in the DXF.
    spaced = {
        pt.value: Pos((i - 2.5) * style.square_size * 0.95, 0)
        * make_piece(pt, scale=style.piece_scale, mode=style.figure_mode,
                     square_size=style.square_size)
        for i, pt in enumerate(PieceType)
    }
    written.append(export_dxf(spaced, dxf_dir / "pieces.dxf"))
    written.append(export_dxf(
        {
            "light": composition.board.light_squares,
            "dark": composition.board.dark_squares,
            "white_pieces": composition.white_pieces,
            "black_pieces": composition.black_pieces,
        },
        dxf_dir / "initial_position.dxf",
    ))

    if with_solids:
        step_dir = root / "step"
        stl_dir = root / "stl"
        board_solid_path = step_dir / "board.step"
        _ensure_parent(board_solid_path)
        export_step(extrude(board.light_squares + board.dark_squares,
                            amount=style.board_thickness), str(board_solid_path))
        written.append(board_solid_path)
        written.append(export_flat_pieces_step(
            step_dir / "flat_pieces.step", style.piece_thickness, style.piece_scale,
            mode=style.figure_mode, square_size=style.square_size))
        for pt in PieceType:
            written.append(export_piece_stl(
                pt, stl_dir / f"{pt.value}.stl", style.piece_thickness, style.piece_scale,
                mode=style.figure_mode, square_size=style.square_size))

    return written
