#!/usr/bin/env python
"""Regenerate every output deliverable (SVG, DXF, STEP, STL).

Usage::

    python scripts/generate_all.py [output_dir] [options]

Formats:

* ``--no-solids`` -- skip the STEP/STL extrusions.
* ``--3mf``       -- also mesh the pieces to ``3mf/pieces.3mf`` for a slicer.

Figure mode (default two-sided):

* ``--single-sided`` -- plain one-orientation silhouettes.
* ``--fused``        -- compact point-symmetric figures readable the same way by
  every player.

Piece style (default ``staunton``):

* ``--style staunton|regence|selenus|st_george|edinburgh|bauhaus|man_ray|glyph|lewis``

Sizes (both default to ``medium``):

* ``--board small|medium|large``   -- 35 / 50 / 65 mm squares.
* ``--figures small|medium|large`` -- how much of a square each piece fills.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from a source checkout without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chess2d.export import generate_all  # noqa: E402
from chess2d.parameters import (  # noqa: E402
    BOARD_SIZE_PRESETS,
    FIGURE_SIZE_PRESETS,
    ChessStyle,
    FigureMode,
    PieceStyle,
)


def _preset(argv: list[str], flag: str, presets: dict[str, float]) -> tuple[str, float]:
    """Read ``--flag <name>`` and map it to a preset value."""
    name = "medium"
    if flag in argv:
        index = argv.index(flag) + 1
        if index >= len(argv):
            raise SystemExit(f"{flag} needs a value: {', '.join(presets)}")
        name = argv[index]
    if name not in presets:
        raise SystemExit(f"unknown {flag} value {name!r}; choose from: {', '.join(presets)}")
    return name, presets[name]


def _choice(argv: list[str], flag: str, enum: type[PieceStyle]) -> PieceStyle:
    """Read ``--flag <value>`` and map it to an enum member."""
    names = [member.value for member in enum]
    value = names[0]
    if flag in argv:
        index = argv.index(flag) + 1
        if index >= len(argv):
            raise SystemExit(f"{flag} needs a value: {', '.join(names)}")
        value = argv[index]
    try:
        return enum(value)
    except ValueError:
        raise SystemExit(
            f"unknown {flag} value {value!r}; choose from: {', '.join(names)}"
        ) from None


def main(argv: list[str]) -> int:
    flag_values = {"--board", "--figures", "--style"}
    skip = {argv[i + 1] for i, a in enumerate(argv) if a in flag_values and i + 1 < len(argv)}
    args = [a for a in argv if not a.startswith("-") and a not in skip]
    with_solids = "--no-solids" not in argv
    with_3mf = "--3mf" in argv
    if "--single-sided" in argv:
        mode = FigureMode.SINGLE
    elif "--fused" in argv:
        mode = FigureMode.FUSED
    else:
        mode = FigureMode.TWO_SIDED
    piece_style = _choice(argv, "--style", PieceStyle)
    board_name, square_size = _preset(argv, "--board", BOARD_SIZE_PRESETS)
    figure_name, piece_scale = _preset(argv, "--figures", FIGURE_SIZE_PRESETS)
    output_dir = args[0] if args else "output"

    style = ChessStyle(
        figure_mode=mode, piece_style=piece_style,
        square_size=square_size, piece_scale=piece_scale,
    )
    print(
        f"Generating chess set into {output_dir!r} "
        f"(solids={with_solids}, 3mf={with_3mf}, style={piece_style.value}, "
        f"figure_mode={mode.value}, board={board_name}, figures={figure_name}) ..."
    )
    written = generate_all(
        output_dir=output_dir, style=style, with_solids=with_solids, with_3mf=with_3mf
    )
    for path in written:
        print(f"  wrote {path}")
    print(f"Done: {len(written)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
