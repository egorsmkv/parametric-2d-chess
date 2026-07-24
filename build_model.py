#!/usr/bin/env python
"""Convenience entry point: regenerate every output deliverable.

Equivalent to ``python scripts/generate_all.py``. Kept at the repo root so the
project can be built with a single top-level command.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from chess2d.export import generate_all  # noqa: E402


def main() -> None:
    written = generate_all()
    print(f"Generated {len(written)} files under output/.")


if __name__ == "__main__":
    main()
