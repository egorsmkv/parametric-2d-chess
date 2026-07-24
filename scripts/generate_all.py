#!/usr/bin/env python
"""Regenerate every output deliverable (SVG, DXF, STEP, STL).

Usage::

    python scripts/generate_all.py [output_dir] [--no-solids] [--single-sided|--fused]

Figure mode (default two-sided):

* ``--single-sided`` -- plain one-orientation silhouettes.
* ``--fused``        -- compact point-symmetric figures readable the same way by
  every player.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from a source checkout without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chess2d.export import generate_all  # noqa: E402
from chess2d.parameters import ChessStyle, FigureMode  # noqa: E402


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    with_solids = "--no-solids" not in argv
    if "--single-sided" in argv:
        mode = FigureMode.SINGLE
    elif "--fused" in argv:
        mode = FigureMode.FUSED
    else:
        mode = FigureMode.TWO_SIDED
    output_dir = args[0] if args else "output"

    style = ChessStyle(figure_mode=mode)
    print(
        f"Generating chess set into {output_dir!r} "
        f"(solids={with_solids}, figure_mode={mode.value}) ..."
    )
    written = generate_all(output_dir=output_dir, style=style, with_solids=with_solids)
    for path in written:
        print(f"  wrote {path}")
    print(f"Done: {len(written)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
