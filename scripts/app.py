#!/usr/bin/env python
"""Launch the Gradio configurator app.

Usage::

    uv sync --extra app
    python scripts/app.py [--port 7860] [--share]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from a source checkout without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chess2d.gradio_app import main  # noqa: E402


def _parse(argv: list[str]) -> dict[str, object]:
    kwargs: dict[str, object] = {}
    if "--share" in argv:
        kwargs["share"] = True
    if "--port" in argv:
        kwargs["server_port"] = int(argv[argv.index("--port") + 1])
    return kwargs


if __name__ == "__main__":
    main(**_parse(sys.argv[1:]))
