"""Optional ocp_vscode preview helpers.

Importing this module never requires ``ocp_vscode``; the dependency is only
touched when :func:`preview_composition` / :func:`preview_pieces` is called.
"""

from __future__ import annotations

import os
import socket

from build123d import Color, Pos

from .assembly import make_initial_position
from .parameters import (
    BLACK_FILL_COLOR,
    DARK_SQUARE_COLOR,
    LIGHT_SQUARE_COLOR,
    PIECE_FILL_Z,
    WHITE_FILL_COLOR,
    ChessStyle,
    FigureMode,
    PieceType,
)
from .pieces import make_piece

# Standard port the ocp_vscode viewer listens on (VS Code extension or
# ``python -m ocp_vscode``). ``get_port()`` returns ``None`` until a viewer has
# announced itself, which otherwise surfaces as an opaque websocket traceback.
_DEFAULT_VIEWER_PORT = 3939

_NO_VIEWER_MESSAGE = (
    "No ocp_vscode viewer is running, so there is nothing to preview to.\n"
    "Start one first, then re-run this command:\n"
    "  * VS Code: open the OCP CAD Viewer panel (install the extension if needed), or\n"
    "  * standalone: run 'python -m ocp_vscode' in another terminal.\n"
    "If the viewer uses a non-default port, set OCP_PORT to match.\n"
    "To generate SVG/DXF/STEP/STL files without a viewer, use "
    "'python scripts/generate_all.py' instead."
)


def _resolve_port() -> int:
    """Best-effort viewer port: an active viewer, then OCP_PORT, then the default."""
    from ocp_vscode import get_port  # noqa: PLC0415

    port = get_port()
    if port:
        return int(port)
    env_port = os.environ.get("OCP_PORT")
    if env_port:
        return int(env_port)
    return _DEFAULT_VIEWER_PORT


def _viewer_reachable(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _show(*args: object, **kwargs: object) -> None:
    try:
        from ocp_vscode import set_port, show  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - viewer is optional
        raise RuntimeError(
            "ocp_vscode is not installed; install it with "
            "'uv sync --extra preview' to use the preview helpers."
        ) from exc

    port = _resolve_port()
    if not _viewer_reachable(port):
        raise RuntimeError(_NO_VIEWER_MESSAGE)
    # Pin the resolved port so show() does not fall back to an unset port.
    set_port(port)
    show(*args, **kwargs)


def preview_composition(style: ChessStyle | None = None) -> None:
    """Show the full initial position in the ocp_vscode viewer."""
    comp = make_initial_position(style if style is not None else ChessStyle())
    _show(
        comp.board.light_squares,
        comp.board.dark_squares,
        Pos(0, 0, PIECE_FILL_Z) * comp.white_pieces,
        Pos(0, 0, PIECE_FILL_Z) * comp.black_pieces,
        names=["light", "dark", "white", "black"],
        colors=[
            Color(*LIGHT_SQUARE_COLOR),
            Color(*DARK_SQUARE_COLOR),
            Color(*WHITE_FILL_COLOR),
            Color(*BLACK_FILL_COLOR),
        ],
    )


def preview_pieces(mode: FigureMode = FigureMode.TWO_SIDED) -> None:
    """Show the six piece silhouettes side by side."""
    shapes = [
        Pos((i - 2.5) * 45.0, 0) * make_piece(pt, mode=mode) for i, pt in enumerate(PieceType)
    ]
    _show(*shapes, names=[pt.value for pt in PieceType])
