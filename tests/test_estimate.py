"""Validation of the 3D-printing material estimate."""

from __future__ import annotations

import math

import pytest

from chess2d.estimate import (
    MATERIALS,
    SOLID_LAYERS,
    PrintSettings,
    cost,
    estimate_set,
    filament_length_mm,
    mass_g,
    piece_counts,
    pieces_per_bed,
    printed_fraction,
    wall_fraction,
)
from chess2d.parameters import BOARD_SIZE_PRESETS, ChessStyle, FigureMode, PieceType
from chess2d.pieces import make_piece, make_piece_solid


def test_piece_counts_make_a_full_set() -> None:
    counts = piece_counts()
    assert sum(counts.values()) == 32
    # Both sides together.
    assert counts[PieceType.PAWN] == 16
    assert counts[PieceType.ROOK] == counts[PieceType.KNIGHT] == 4
    assert counts[PieceType.BISHOP] == 4
    assert counts[PieceType.QUEEN] == counts[PieceType.KING] == 2


@pytest.mark.parametrize("piece_type", list(PieceType))
def test_estimated_volume_matches_the_exported_solid(piece_type: PieceType) -> None:
    # The quoted volume must equal the STL the user actually prints. Sketch.area
    # is not enough: a self-overlapping figure double-counts the overlap (the
    # knight is 5% out), so the estimate measures the extruded solid instead.
    thickness = 2.0
    estimate = estimate_set(ChessStyle(piece_thickness=thickness))
    part = next(p for p in estimate.pieces if p.name == piece_type.value)
    solid = make_piece_solid(piece_type, thickness=thickness)
    assert part.solid_volume_mm3 == pytest.approx(solid.volume, rel=1e-9)


def test_knight_is_not_over_counted_by_face_area() -> None:
    # Regression: the knight's two-sided figure self-overlaps.
    thickness = 2.0
    estimate = estimate_set(ChessStyle(piece_thickness=thickness))
    knight = next(p for p in estimate.pieces if p.name == PieceType.KNIGHT.value)
    naive_area = make_piece(PieceType.KNIGHT).area
    assert knight.area_mm2 < naive_area
    assert knight.solid_volume_mm3 == pytest.approx(
        make_piece_solid(PieceType.KNIGHT, thickness=thickness).volume, rel=1e-9,
    )


def test_estimate_measures_every_piece() -> None:
    estimate = estimate_set()
    assert len(estimate.pieces) == len(PieceType)
    assert estimate.piece_count == 32
    for part in estimate.pieces:
        assert part.area_mm2 > 0
        assert part.perimeter_mm > 0
        assert part.solid_volume_mm3 > 0


@pytest.mark.parametrize("square_size", list(BOARD_SIZE_PRESETS.values()))
def test_material_scales_with_board_size(square_size: float) -> None:
    small = estimate_set(ChessStyle(square_size=BOARD_SIZE_PRESETS["small"]))
    scaled = estimate_set(ChessStyle(square_size=square_size))
    assert scaled.pieces_solid_mm3 >= small.pieces_solid_mm3 * 0.999


def test_thicker_pieces_need_proportionally_more_material() -> None:
    thin = estimate_set(ChessStyle(piece_thickness=2.0))
    thick = estimate_set(ChessStyle(piece_thickness=4.0))
    assert thick.pieces_solid_mm3 == pytest.approx(thin.pieces_solid_mm3 * 2.0, rel=1e-9)


def test_printed_volume_never_exceeds_solid() -> None:
    for mode in FigureMode:
        estimate = estimate_set(ChessStyle(figure_mode=mode))
        assert estimate.pieces_printed_mm3 <= estimate.pieces_solid_mm3


def test_thin_parts_come_out_solid_whatever_the_infill() -> None:
    # A part no taller than the solid top+bottom stack has no sparse layers.
    settings = PrintSettings(layer_height_mm=0.3, infill=0.0)
    thickness = SOLID_LAYERS * settings.layer_height_mm
    assert printed_fraction(300.0, 150.0, thickness, settings) == 1.0


def test_infill_matters_once_a_part_is_thick_enough() -> None:
    thick = 12.0
    low = printed_fraction(300.0, 150.0, thick, PrintSettings(infill=0.1))
    high = printed_fraction(300.0, 150.0, thick, PrintSettings(infill=0.9))
    assert low < high < 1.0


def test_walls_alone_can_fill_a_narrow_section() -> None:
    settings = PrintSettings()
    # A sliver: perimeter huge relative to area -> saturates at 1.0.
    assert wall_fraction(area_mm2=5.0, perimeter_mm=500.0, settings=settings) == 1.0
    # A wide part: walls are a small share.
    assert wall_fraction(area_mm2=10_000.0, perimeter_mm=400.0, settings=settings) < 0.1


def test_more_infill_means_more_material() -> None:
    style = ChessStyle()
    lean = estimate_set(style, PrintSettings(infill=0.1))
    dense = estimate_set(style, PrintSettings(infill=0.9))
    assert dense.pieces_printed_mm3 > lean.pieces_printed_mm3


def test_mass_length_and_cost_formulae() -> None:
    assert mass_g(1000.0, 1.24) == pytest.approx(1.24)  # 1 cm3 of PLA
    # 1.75 mm filament: 1 m holds pi*(0.875^2)*1000 mm3.
    volume = math.pi * 0.875**2 * 1000
    assert filament_length_mm(volume, 1.75) == pytest.approx(1000.0)
    assert cost(500.0, 20.0) == pytest.approx(10.0)


def test_denser_material_weighs_more_for_the_same_volume() -> None:
    volume = 24_000.0
    heavy = mass_g(volume, MATERIALS["PETG"].density_g_cm3)
    light = mass_g(volume, MATERIALS["ABS"].density_g_cm3)
    assert heavy > light


def test_budget_adds_a_margin_over_the_solid_figure() -> None:
    estimate = estimate_set()
    _, solid_mass = estimate.mass_range_g()
    assert estimate.budget_mass_g() > solid_mass


def test_ranges_are_ordered() -> None:
    estimate = estimate_set()
    for low, high in (
        estimate.mass_range_g(),
        estimate.filament_range_m(),
        estimate.cost_range(),
    ):
        assert 0 < low <= high


def test_board_is_measured_separately_and_is_large() -> None:
    estimate = estimate_set()
    # 8x8 squares of 50 mm tile the playing surface exactly.
    assert estimate.board.area_mm2 == pytest.approx(160_000.0)
    assert estimate.board.total_solid_mm3() > estimate.pieces_solid_mm3


def test_pieces_per_bed_is_sane() -> None:
    assert pieces_per_bed(378.0) > 1
    assert pieces_per_bed(10_000_000.0) == 0
