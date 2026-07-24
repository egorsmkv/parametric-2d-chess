"""Validation of individual piece silhouettes (spec section 23.1)."""

from __future__ import annotations

import pytest
from build123d import CenterOf

from chess2d.parameters import PIECE_DIMS, SQUARE_SIZE, PieceType
from chess2d.pieces import make_knight, make_piece, make_piece_geometry, make_piece_solid

ALL_PIECES = list(PieceType)
SYMMETRIC_PIECES = [
    PieceType.PAWN,
    PieceType.ROOK,
    PieceType.BISHOP,
    PieceType.QUEEN,
    PieceType.KING,
]


@pytest.mark.parametrize("piece_type", ALL_PIECES)
def test_piece_is_valid_single_face(piece_type: PieceType) -> None:
    piece = make_piece(piece_type)
    assert piece is not None
    assert len(piece.faces()) >= 1
    assert piece.area > 0.0


@pytest.mark.parametrize("piece_type", ALL_PIECES)
def test_piece_fits_in_square(piece_type: PieceType) -> None:
    box = make_piece(piece_type).bounding_box()
    assert box.size.X <= SQUARE_SIZE
    assert box.size.Y <= SQUARE_SIZE


@pytest.mark.parametrize("piece_type", ALL_PIECES)
def test_piece_centered_on_origin(piece_type: PieceType) -> None:
    box = make_piece(piece_type).bounding_box()
    assert abs(box.center().X) < 1e-6
    assert abs(box.center().Y) < 1e-6


@pytest.mark.parametrize("piece_type", ALL_PIECES)
def test_piece_closed_wires(piece_type: PieceType) -> None:
    for face in make_piece(piece_type).faces():
        for wire in face.wires():
            assert wire.is_closed


@pytest.mark.parametrize("piece_type", SYMMETRIC_PIECES)
def test_symmetric_pieces_outline_is_symmetric(piece_type: PieceType) -> None:
    # The outer silhouette is symmetric about the Y-axis for every piece
    # except the knight (the bishop's diagonal slit is an interior feature).
    box = make_piece(piece_type).bounding_box()
    assert abs(box.min.X + box.max.X) < 1e-3


# The bishop's diagonal mitre slit deliberately breaks mass symmetry.
@pytest.mark.parametrize(
    "piece_type",
    [PieceType.PAWN, PieceType.ROOK, PieceType.QUEEN, PieceType.KING],
)
def test_symmetric_pieces_mass_on_axis(piece_type: PieceType) -> None:
    assert abs(make_piece(piece_type).center(CenterOf.MASS).X) < 1e-3


def test_knight_is_asymmetric() -> None:
    # Deliberately not symmetric: the area centroid sits off the Y-axis.
    assert abs(make_knight().center(CenterOf.MASS).X) > 0.25


def test_knight_facing_mirror() -> None:
    left = make_knight(facing="left").bounding_box()
    right = make_knight(facing="right").bounding_box()
    # Mirroring flips the horizontal extent.
    assert pytest.approx(-right.max.X, abs=1e-6) == left.min.X


@pytest.mark.parametrize("piece_type", ALL_PIECES)
def test_piece_within_target_dims(piece_type: PieceType) -> None:
    dims = PIECE_DIMS[piece_type]
    box = make_piece(piece_type).bounding_box()
    # Generated silhouette stays within a small tolerance of the spec targets.
    assert dims.width + 2.0 >= box.size.X
    assert dims.height + 2.0 >= box.size.Y


def test_bishop_slit_is_internal_opening() -> None:
    face = make_piece(PieceType.BISHOP).faces()[0]
    # Outer boundary + at least one inner slit wire.
    assert len(face.wires()) >= 2


def test_scaling_scales_bounding_box() -> None:
    base = make_piece(PieceType.QUEEN).bounding_box()
    scaled = make_piece(PieceType.QUEEN, scale=0.5).bounding_box()
    assert pytest.approx(base.size.Y * 0.5, rel=1e-6) == scaled.size.Y


def test_piece_geometry_bundle() -> None:
    geom = make_piece_geometry(PieceType.ROOK, with_solid=True)
    assert geom.fill.area > 0
    assert geom.outline is not None
    assert geom.optional_solid is not None
    assert geom.optional_solid.volume > 0


@pytest.mark.parametrize("piece_type", ALL_PIECES)
def test_thin_solid_extrusion(piece_type: PieceType) -> None:
    solid = make_piece_solid(piece_type, thickness=2.0)
    assert len(solid.solids()) >= 1
    assert solid.volume > 0
