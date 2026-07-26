"""Invariants every piece style must satisfy, in every figure mode.

The style-specific look is a design choice, but these properties are what make a
set usable: one connected piece per figure, inside its square, and legible enough
that the six ranks cannot be confused.
"""

from __future__ import annotations

import itertools

import pytest

from chess2d.parameters import (
    BOARD_SIZE_PRESETS,
    SQUARE_SIZE,
    ChessStyle,
    FigureMode,
    PieceStyle,
    PieceType,
)
from chess2d.pieces import make_piece, make_piece_solid
from chess2d.styles import STYLES

STYLES_AND_MODES = list(itertools.product(PieceStyle, FigureMode))


def test_every_style_is_registered_with_all_six_generators() -> None:
    for style in PieceStyle:
        spec = STYLES[style]
        assert spec.label and spec.note
        assert set(spec.generators) == set(PieceType)


@pytest.mark.parametrize(("style", "mode"), STYLES_AND_MODES)
@pytest.mark.parametrize("piece_type", list(PieceType))
def test_piece_is_a_single_connected_face(
    piece_type: PieceType, style: PieceStyle, mode: FigureMode,
) -> None:
    # The printability rule: one piece must come off the bed or cutter as one
    # part, with a positive area and closed boundaries.
    piece = make_piece(piece_type, mode=mode, style=style)
    assert piece.area > 0.0
    assert len(piece.faces()) == 1
    for wire in piece.wires():
        assert wire.is_closed


@pytest.mark.parametrize(("style", "mode"), STYLES_AND_MODES)
@pytest.mark.parametrize("square_size", list(BOARD_SIZE_PRESETS.values()))
def test_pieces_fit_their_square(style: PieceStyle, mode: FigureMode, square_size: float) -> None:
    for piece_type in PieceType:
        box = make_piece(piece_type, mode=mode, style=style, square_size=square_size).bounding_box()
        assert square_size + 1e-6 >= box.size.X
        assert square_size + 1e-6 >= box.size.Y


@pytest.mark.parametrize(("style", "mode"), STYLES_AND_MODES)
def test_pieces_are_centred(style: PieceStyle, mode: FigureMode) -> None:
    for piece_type in PieceType:
        box = make_piece(piece_type, mode=mode, style=style).bounding_box()
        assert abs(box.center().X) < 1e-6
        assert abs(box.center().Y) < 1e-6


@pytest.mark.parametrize(("style", "mode"), STYLES_AND_MODES)
def test_pieces_extrude_to_solids(style: PieceStyle, mode: FigureMode) -> None:
    for piece_type in PieceType:
        solid = make_piece_solid(piece_type, thickness=2.0, mode=mode, style=style)
        assert len(solid.solids()) >= 1
        assert solid.volume > 0


#: Highest tolerated silhouette overlap between two different ranks. The worst
#: legitimate pair measured across all styles and modes is 0.86 (Selenus
#: two-sided pawn/rook), so this leaves headroom while still catching a genuine
#: collapse -- fusing geometric pieces without per-style tuning scores 0.99.
MAX_PAIR_OVERLAP = 0.90


def _overlap(first: object, second: object) -> float:
    """Intersection over union of two silhouettes: 1.0 means identical."""
    intersection = first & second  # type: ignore[operator]
    shared = intersection.area if intersection is not None else 0.0
    return shared / (first.area + second.area - shared)  # type: ignore[attr-defined]


@pytest.mark.parametrize(("style", "mode"), STYLES_AND_MODES)
def test_the_six_pieces_are_visually_distinguishable(style: PieceStyle, mode: FigureMode) -> None:
    """No two ranks may resolve to near-identical shapes.

    Compares the silhouettes themselves rather than area and bounding box: in
    the fitted modes every piece is scaled to the same height, so those coarse
    numbers cannot tell a knight's head from a queen's crown.

    This is the guard that every style x mode combination is playable. It is
    what proves the per-style ``fused_keep`` tuning works, and it is why the
    Bauhaus pawn is a triangle rather than Hartwig's small cube -- a piece
    distinguished from the rook only by size collapses onto it once every figure
    is fitted to the same square.
    """
    pieces = {
        piece_type: make_piece(piece_type, mode=mode, style=style) for piece_type in PieceType
    }
    for left, right in itertools.combinations(PieceType, 2):
        overlap = _overlap(pieces[left], pieces[right])
        assert overlap < MAX_PAIR_OVERLAP, (
            f"{style.value}/{mode.value}: {left.value} and {right.value} overlap "
            f"{overlap:.3f} of their combined area -- too alike to tell apart"
        )


@pytest.mark.parametrize("style", list(PieceStyle))
def test_knight_is_asymmetric_in_every_style(style: PieceStyle) -> None:
    # Two-sided composition relies on the knight having a handedness.
    left = make_piece(PieceType.KNIGHT, mode=FigureMode.SINGLE, style=style)
    right = make_piece(PieceType.KNIGHT, mode=FigureMode.SINGLE, style=style, mirrored=True)
    left_box, right_box = left.bounding_box(), right.bounding_box()
    assert pytest.approx(left_box.size.X, abs=1e-6) == right_box.size.X
    # A symmetric shape would be unchanged by mirroring; these must differ.
    assert (
        abs(left.center().X - right.center().X) > 1e-3
        or pytest.approx(right_box.min.X, abs=1e-9) != left_box.min.X
    )


@pytest.mark.parametrize("style", list(PieceStyle))
def test_native_pieces_share_a_height_range(style: PieceStyle) -> None:
    """Styles must be authored at the same native scale.

    ``SINGLE`` mode scales by ``square_size / SQUARE_SIZE`` rather than fitting,
    so a style drawn much smaller or larger than the others would look wrong on
    the board instead of merely different.
    """
    heights = [
        make_piece(pt, mode=FigureMode.SINGLE, style=style).bounding_box().size.Y
        for pt in PieceType
    ]
    assert min(heights) > SQUARE_SIZE * 0.35
    assert max(heights) < SQUARE_SIZE * 0.95
    # The king should not be the shortest piece in any style.
    king = make_piece(PieceType.KING, mode=FigureMode.SINGLE, style=style).bounding_box().size.Y
    assert king == pytest.approx(max(heights), rel=1e-9)


@pytest.mark.parametrize("style", list(PieceStyle))
def test_full_position_places_thirty_two_separate_pieces(style: PieceStyle) -> None:
    from chess2d.assembly import make_initial_position  # noqa: PLC0415

    composition = make_initial_position(ChessStyle(piece_style=style))
    assert len(composition.white_pieces.faces()) == 16
    assert len(composition.black_pieces.faces()) == 16
