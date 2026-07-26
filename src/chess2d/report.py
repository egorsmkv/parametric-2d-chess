"""Render a 3D-printing material report as a PDF.

``reportlab`` is imported lazily so the core package keeps depending only on
build123d (the same optional-dependency pattern :mod:`chess2d.preview` uses for
``ocp_vscode``). Install it with the ``app`` extra.

The arithmetic lives in :mod:`chess2d.estimate`; this module only lays it out.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .board import BOARD_SQUARES
from .estimate import (
    BED_PACKING_EFFICIENCY,
    DEFAULT_BED_MM,
    MATERIALS,
    SOLID_LAYERS,
    WASTE_MARGIN,
    PrintSettings,
    SetEstimate,
    cost,
    estimate_set,
    filament_length_mm,
    mass_g,
    pieces_per_bed,
    printed_fraction,
    wall_fraction,
)
from .parameters import (
    DARK_SQUARE_COLOR,
    LIGHT_SQUARE_COLOR,
    ChessStyle,
    FigureMode,
)
from .styles import STYLES

if TYPE_CHECKING:  # pragma: no cover - typing only
    from reportlab.platypus import Flowable

_MODE_NAMES = {
    FigureMode.TWO_SIDED: "Two-sided",
    FigureMode.FUSED: "Fused",
    FigureMode.SINGLE: "Single-sided",
}


def _today() -> date:
    """Today in the local timezone, resolved via UTC so it is never naive."""
    return datetime.now(timezone.utc).astimezone().date()


def _styles() -> Any:
    from reportlab.lib.enums import TA_LEFT  # noqa: PLC0415
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: PLC0415

    sheet = getSampleStyleSheet()
    sheet.add(
        ParagraphStyle(
            "C2Title",
            parent=sheet["Title"],
            fontSize=19,
            spaceAfter=2,
            alignment=TA_LEFT,
        ),
    )
    sheet.add(
        ParagraphStyle(
            "C2Sub",
            parent=sheet["Normal"],
            fontSize=9,
            textColor="#666666",
            spaceAfter=10,
        ),
    )
    sheet.add(
        ParagraphStyle(
            "C2H",
            parent=sheet["Heading2"],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=5,
        ),
    )
    sheet.add(
        ParagraphStyle(
            "C2Body",
            parent=sheet["Normal"],
            fontSize=9,
            leading=13,
            spaceAfter=5,
        ),
    )
    sheet.add(
        ParagraphStyle(
            "C2Small",
            parent=sheet["Normal"],
            fontSize=8,
            leading=11,
            textColor="#555555",
        ),
    )
    sheet.add(
        ParagraphStyle(
            "C2Formula",
            parent=sheet["Normal"],
            fontName="Courier",
            fontSize=7.5,
            leading=10,
        ),
    )
    sheet.add(
        ParagraphStyle(
            "C2Worked",
            parent=sheet["C2Formula"],
            textColor="#3d5a1e",
        ),
    )
    return sheet


def _table(data: list[list[str]], widths: list[float], header: bool = True) -> Any:
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.platypus import Table, TableStyle  # noqa: PLC0415

    table = Table(data, colWidths=widths, hAlign="LEFT")
    commands = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#dddddd")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]
    if header:
        commands += [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef0e9")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#8a9a63")),
        ]
    table.setStyle(TableStyle(commands))
    return table


def _side_by_side(left: Any, right: Any, widths: list[float] | None = None) -> Any:
    """Place two flowables in one row, top-aligned and without borders."""
    from reportlab.platypus import Table, TableStyle  # noqa: PLC0415

    holder = Table([[left, right]], colWidths=widths or [200, 205], hAlign="LEFT")
    holder.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ],
        ),
    )
    return holder


class _BoardDiagram:
    """Factory for a small 8x8 board drawing using the project's own colours."""

    @staticmethod
    def build(size_pt: float) -> Any:
        from reportlab.graphics.shapes import Drawing, Rect  # noqa: PLC0415
        from reportlab.lib.colors import Color  # noqa: PLC0415

        drawing = Drawing(size_pt, size_pt)
        cell = size_pt / BOARD_SQUARES
        light = Color(*LIGHT_SQUARE_COLOR)
        dark = Color(*DARK_SQUARE_COLOR)
        for rank in range(BOARD_SQUARES):
            for file in range(BOARD_SQUARES):
                # h1 (lower right from White) is light -- same parity as board.py.
                fill = dark if (file + rank) % 2 == 0 else light
                drawing.add(
                    Rect(
                        file * cell,
                        rank * cell,
                        cell,
                        cell,
                        fillColor=fill,
                        strokeColor=None,
                    ),
                )
        return drawing


def _configuration_rows(estimate: SetEstimate) -> list[list[str]]:
    style = estimate.style
    playing = style.square_size * BOARD_SQUARES
    return [
        ["Setting", "Value"],
        ["Piece style", STYLES[style.piece_style].label],
        ["Figure form", _MODE_NAMES[style.figure_mode]],
        ["Square size", f"{style.square_size:g} mm"],
        ["Playing surface", f"{playing:g} x {playing:g} mm"],
        ["Figure scale", f"{style.piece_scale:g}x"],
        ["Piece thickness", f"{style.piece_thickness:g} mm"],
        ["Board thickness", f"{style.board_thickness:g} mm"],
        ["Pieces in a set", f"{estimate.piece_count}"],
    ]


def _settings_rows(settings: PrintSettings) -> list[list[str]]:
    material = MATERIALS[settings.material]
    return [
        ["Setting", "Value"],
        ["Material", f"{material.name} ({material.density_g_cm3:g} g/cm3)"],
        ["Filament diameter", f"{settings.filament_diameter_mm:g} mm"],
        ["Layer height", f"{settings.layer_height_mm:g} mm"],
        ["Infill", f"{settings.infill:.0%}"],
        ["Perimeters", f"{settings.wall_count} x {settings.line_width_mm:g} mm"],
        ["Price", f"{settings.price_per_kg:g} per kg"],
    ]


def _headline(estimate: SetEstimate, sheet: Any) -> list[Any]:
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.platypus import Paragraph, Table, TableStyle  # noqa: PLC0415

    mass_low, mass_high = estimate.mass_range_g()
    len_low, len_high = estimate.filament_range_m()
    cost_low, cost_high = estimate.cost_range()
    resin = estimate.settings.material.startswith("Resin")

    cells = [
        ["Material volume", "Mass", "Filament" if not resin else "Volume", "Cost"],
        [
            f"{estimate.pieces_printed_mm3 / 1000:.1f}-{estimate.pieces_solid_mm3 / 1000:.1f} cm3",
            f"{mass_low:.0f}-{mass_high:.0f} g",
            f"{len_low:.1f}-{len_high:.1f} m"
            if not resin
            else f"{estimate.pieces_solid_mm3 / 1000:.1f} ml",
            f"{cost_low:.2f}-{cost_high:.2f}",
        ],
    ]
    table = Table(cells, colWidths=[115, 95, 95, 95], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f4ec")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#8a9a63")),
                ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#5f6b45")),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 13),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ],
        ),
    )
    return [
        table,
        Paragraph(
            f"Budget about <b>{estimate.budget_mass_g():.0f} g</b> "
            f"({estimate.settings.material}) to print all {estimate.piece_count} pieces "
            f"-- the solid figure plus {WASTE_MARGIN:.0%} for purge and mishaps.",
            sheet["C2Small"],
        ),
    ]


def _piece_table(estimate: SetEstimate) -> Any:
    settings = estimate.settings
    density = settings.density_g_cm3
    rows = [["Piece", "Qty", "Area", "Each", "Total", "Mass"]]
    for part in estimate.pieces:
        total = part.total_solid_mm3()
        rows.append(
            [
                part.name.capitalize(),
                str(part.count),
                f"{part.area_mm2:.0f} mm2",
                f"{part.solid_volume_mm3 / 1000:.2f} cm3",
                f"{total / 1000:.2f} cm3",
                f"{mass_g(total, density):.1f} g",
            ],
        )
    rows.append(
        [
            "All pieces",
            str(estimate.piece_count),
            "",
            "",
            f"{estimate.pieces_solid_mm3 / 1000:.2f} cm3",
            f"{mass_g(estimate.pieces_solid_mm3, density):.1f} g",
        ],
    )
    table = _table(rows, [80, 35, 70, 75, 75, 60])
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.platypus import TableStyle  # noqa: PLC0415

    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.HexColor("#8a9a63")),
            ],
        ),
    )
    return table


def _material_table(estimate: SetEstimate) -> Any:
    """Same solid volume priced across every material.

    No filament column: length depends on volume and diameter only, so it is
    identical for every filament (and meaningless for resin) -- it is stated
    once in the surrounding note instead.
    """
    volume = estimate.pieces_solid_mm3
    settings = estimate.settings
    rows = [["Material", "Density", "Mass", "Cost at your price", "Notes"]]
    for material in MATERIALS.values():
        grams = mass_g(volume, material.density_g_cm3)
        rows.append(
            [
                material.name,
                f"{material.density_g_cm3:g} g/cm3",
                f"{grams:.0f} g",
                f"{cost(grams, settings.price_per_kg):.2f}",
                material.note,
            ],
        )
    table = _table(rows, [70, 62, 45, 85, 200])
    from reportlab.platypus import TableStyle  # noqa: PLC0415

    table.setStyle(TableStyle([("ALIGN", (4, 0), (4, -1), "LEFT")]))
    return table


def _formula_block(estimate: SetEstimate, sheet: Any) -> list[Any]:
    """The worked formulae.

    Cells are Paragraphs, not bare strings: only Paragraphs wrap inside a column
    (bare strings overflow into the neighbouring one). Formulae stay plain ASCII
    so they read the same in the PDF as when retyped into a calculator.
    """
    from reportlab.platypus import Paragraph  # noqa: PLC0415

    settings = estimate.settings
    sample = estimate.pieces[0]
    walls = wall_fraction(sample.area_mm2, sample.perimeter_mm, settings)
    fraction = printed_fraction(sample.area_mm2, sample.perimeter_mm, sample.thickness_mm, settings)
    layers = max(1, round(sample.thickness_mm / settings.layer_height_mm))
    density = settings.density_g_cm3
    volume = estimate.pieces_solid_mm3

    length_m = filament_length_mm(volume, settings.filament_diameter_mm) / 1000.0
    grams = mass_g(volume, density)
    # (label, formula, worked example with this configuration's real numbers)
    lines = [
        (
            "Solid volume of a part",
            "V = A * t",
            (
                f"{sample.name}: {sample.area_mm2:.0f} mm2 * {sample.thickness_mm:g} mm "
                f"= {sample.solid_volume_mm3:.0f} mm3"
            ),
        ),
        (
            "Wall share of a layer",
            "w = min(1, P * walls * line_width / A)",
            (
                f"{sample.perimeter_mm:.0f} * {settings.wall_count} * "
                f"{settings.line_width_mm:g} / {sample.area_mm2:.0f} = {walls:.2f}"
            ),
        ),
        (
            "Sparse-infill correction",
            "f = [n_solid + (n - n_solid) * (w + (1 - w) * infill)] / n",
            (
                f"n = ceil(t / h) = {layers}, n_solid = {min(SOLID_LAYERS, layers)}, "
                f"so f = {fraction:.2f}"
            ),
        ),
        (
            "Mass",
            "m = V / 1000 * density",
            f"{volume:.0f} / 1000 * {density:g} = {grams:.0f} g",
        ),
        (
            "Filament length",
            "L = V / (pi * (d / 2)^2)",
            f"{volume:.0f} / (pi * ({settings.filament_diameter_mm:g}/2)^2) = {length_m:.1f} m",
        ),
        (
            "Cost",
            "C = m / 1000 * price_per_kg",
            (
                f"{grams:.0f} / 1000 * {settings.price_per_kg:g} = "
                f"{cost(grams, settings.price_per_kg):.2f}"
            ),
        ),
        (
            "Parts per bed",
            "N = floor(bed_area * packing / A)",
            (
                f"{DEFAULT_BED_MM[0]:g} * {DEFAULT_BED_MM[1]:g} * "
                f"{BED_PACKING_EFFICIENCY:g} / {sample.area_mm2:.0f} "
                f"= {pieces_per_bed(sample.area_mm2)}"
            ),
        ),
    ]

    rows: list[list[Any]] = [["Quantity", "Formula", "This configuration"]]
    rows += [
        [
            Paragraph(label, sheet["C2Body"]),
            Paragraph(formula, sheet["C2Formula"]),
            Paragraph(worked, sheet["C2Worked"]),
        ]
        for label, formula, worked in lines
    ]
    table = _table(rows, [92, 178, 168])
    from reportlab.platypus import TableStyle  # noqa: PLC0415

    table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 1), (-1, -1), 5),
            ],
        ),
    )
    return [table]


def _board_section(estimate: SetEstimate, sheet: Any) -> list[Any]:
    from reportlab.platypus import Paragraph  # noqa: PLC0415

    board = estimate.board
    density = estimate.settings.density_g_cm3
    volume = board.total_solid_mm3()
    grams = mass_g(volume, density)
    rows = [
        ["Quantity", "Value"],
        ["Playing surface area", f"{board.area_mm2:.0f} mm2"],
        ["Thickness", f"{board.thickness_mm:g} mm"],
        ["Solid volume", f"{volume / 1000:.0f} cm3"],
        [f"Mass ({estimate.settings.material})", f"{grams:.0f} g"],
        ["Cost", f"{cost(grams, estimate.settings.price_per_kg):.2f}"],
    ]
    return [
        Paragraph("The board is a different scale", sheet["C2H"]),
        Paragraph(
            f"Printing the playing surface needs roughly <b>{grams:.0f} g</b> -- around "
            f"{grams / max(estimate.mass_range_g()[1], 1e-9):.0f}x the whole set of "
            "pieces, and it will not fit on one bed. Most people cut the board from "
            "plywood or acrylic with the supplied DXF/SVG, or print it in tiles.",
            sheet["C2Body"],
        ),
        _table(rows, [150, 110]),
    ]


def _practical_notes(estimate: SetEstimate, sheet: Any) -> list[Any]:
    from reportlab.platypus import Paragraph  # noqa: PLC0415

    smallest = min(estimate.pieces, key=lambda part: part.area_mm2)
    per_bed = pieces_per_bed(max(part.area_mm2 for part in estimate.pieces))
    layers = max(1, round(estimate.style.piece_thickness / estimate.settings.layer_height_mm))
    notes = [
        (
            "These are flat parts: print them lying on the bed. No supports are needed and "
            "the silhouette is a single connected piece, so nothing comes loose."
        ),
        (
            f"At {estimate.settings.layer_height_mm:g} mm layers each piece is about "
            f"{layers} layers tall. Slicers lay {SOLID_LAYERS} solid layers top and bottom, "
            "so below that thickness the part is effectively solid whatever the infill."
        ),
        (
            f"Roughly {per_bed} pieces fit on a "
            f"{DEFAULT_BED_MM[0]:g}x{DEFAULT_BED_MM[1]:g} mm bed at "
            f"{BED_PACKING_EFFICIENCY:.0%} packing, so the set takes a few batches."
        ),
        (
            "First-layer squish (elephant's foot) widens the base slightly. If the pieces "
            "feel tight on the squares, add a small horizontal expansion of -0.1 mm."
        ),
        (
            f"The narrowest piece is the {smallest.name} at {smallest.area_mm2:.0f} mm2 of "
            "footprint; use at least two perimeters so thin necks stay solid. Spools are "
            "sold in 500 g and 1 kg units, so one covers many sets."
        ),
    ]
    return [Paragraph(f"&bull; {note}", sheet["C2Body"]) for note in notes]


def write_material_report(
    path: str | Path,
    style: ChessStyle | None = None,
    settings: PrintSettings | None = None,
    estimate: SetEstimate | None = None,
) -> Path:
    """Write the 3D-printing material report and return the path.

    Pass ``estimate`` to reuse an already-measured set; otherwise it is computed
    from ``style`` and ``settings``.
    """
    from reportlab.lib.pagesizes import A4  # noqa: PLC0415
    from reportlab.lib.units import mm  # noqa: PLC0415
    from reportlab.platypus import (  # noqa: PLC0415
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    if estimate is None:
        estimate = estimate_set(style, settings)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet = _styles()

    document = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        title="3D printing material estimate - 2D chess set",
        author="chess2d",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    story: list[Flowable] = [
        Paragraph("3D printing material estimate", sheet["C2Title"]),
        Paragraph(
            f"Parametric 2D chess set &middot; generated {_today().isoformat()}. "
            "Planning figures worked out from the exact exported geometry -- helpful "
            "for buying material, but not a substitute for slicing the STL files.",
            sheet["C2Sub"],
        ),
        *_headline(estimate, sheet),
        Spacer(1, 10),
        Paragraph("Your configuration and print settings", sheet["C2H"]),
        # Side by side: two short tables stacked would push a third page.
        _side_by_side(
            _table(_configuration_rows(estimate), [95, 100]),
            _table(_settings_rows(estimate.settings), [90, 110]),
        ),
        Spacer(1, 8),
        _side_by_side(
            _BoardDiagram.build(58),
            Paragraph(
                f"The {BOARD_SQUARES}&times;{BOARD_SQUARES} layout these pieces are "
                "sized for. Each silhouette is scaled to its square, so the whole set "
                "grows and shrinks with the board size above.",
                sheet["C2Small"],
            ),
            widths=[70, 330],
        ),
        Paragraph("Per piece", sheet["C2H"]),
        Paragraph(
            "Volumes are fully solid (the upper bound). Quantities cover both sides.",
            sheet["C2Small"],
        ),
        Spacer(1, 4),
        _piece_table(estimate),
        PageBreak(),
        Paragraph("How these numbers are worked out", sheet["C2H"]),
        Paragraph(
            "Area and perimeter are measured from the real silhouettes, so only the "
            "printing model is approximate. A sparse-infill print falls between the "
            "two bounds quoted above; buy for the solid figure.",
            sheet["C2Body"],
        ),
        *_formula_block(estimate, sheet),
        Paragraph("Other materials", sheet["C2H"]),
        Paragraph(
            f"The same solid volume in other stock. Filament length does not depend on "
            f"the material -- it is "
            f"{filament_length_mm(estimate.pieces_solid_mm3, estimate.settings.filament_diameter_mm) / 1000:.1f} m "  # noqa: E501
            f"of {estimate.settings.filament_diameter_mm:g} mm filament in every case, "
            "and resin is sold by volume. Costs below all use the one price you entered; "
            "real prices differ per material.",
            sheet["C2Small"],
        ),
        Spacer(1, 4),
        _material_table(estimate),
        # Explicit break so the closing page is a coherent "board + practice"
        # section rather than a couple of bullets orphaned after the tables.
        PageBreak(),
        *_board_section(estimate, sheet),
        Paragraph("Practical notes", sheet["C2H"]),
        *_practical_notes(estimate, sheet),
    ]

    document.build(story)
    return out
