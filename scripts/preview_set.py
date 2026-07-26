#!/usr/bin/env python
"""Open the full chess composition in the ocp_vscode viewer.

Usage::

    python scripts/preview_set.py [pieces]

With no argument the full initial position is shown; pass ``pieces`` to show
the six silhouettes side by side instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chess2d.preview import preview_composition, preview_pieces


def main(argv: list[str]) -> int:
    try:
        if argv and argv[0] == "pieces":
            preview_pieces()
        else:
            preview_composition()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
