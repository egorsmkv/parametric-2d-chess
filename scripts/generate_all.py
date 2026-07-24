#!/usr/bin/env python
"""Regenerate every output deliverable (SVG, DXF, STEP, STL).

Usage::

    python scripts/generate_all.py [output_dir] [--no-solids]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from a source checkout without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chess2d.export import generate_all  # noqa: E402
from chess2d.parameters import ChessStyle  # noqa: E402


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("-")]
    with_solids = "--no-solids" not in argv
    output_dir = args[0] if args else "output"

    print(f"Generating chess set into {output_dir!r} (solids={with_solids}) ...")
    written = generate_all(output_dir=output_dir, style=ChessStyle(), with_solids=with_solids)
    for path in written:
        print(f"  wrote {path}")
    print(f"Done: {len(written)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
