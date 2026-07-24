# Parametric 2D Chess Set (build123d)

A complete **2D chessboard and flat chess-piece silhouettes** generated entirely
from Python with [build123d](https://build123d.readthedocs.io). The project
reproduces the classic composition — an 8×8 cream/green board with the standard
opening arrangement, White at the bottom and Black at the top — as stylised flat
symbols rather than sculpted 3D geometry.

Each piece is available in three forms:

1. **Filled 2D face** — for rendering, SVG export, engraving or colouring.
2. **Outline** — closed boundary wires (or an offset ring) for laser cutting / plotting.
3. **Optional thin solid** — the face extruded into a flat token for cutting or 3D printing.

## Quick start

```bash
uv sync
python scripts/generate_all.py      # writes everything under output/
```

That single command regenerates all deliverables:

```
output/
├── svg/   board.svg, <piece>.svg ×6, initial_position.svg
├── dxf/   board.dxf, pieces.dxf, initial_position.dxf
├── step/  board.step, flat_pieces.step
└── stl/   <piece>.stl ×6
```

Flags:

* `--no-solids` — skip the STEP/STL extrusions.
* `--single-sided` — plain single-sided silhouettes instead of the default
  two-sided figures.
* a positional argument sets the output directory.

```bash
python scripts/generate_all.py my_output --no-solids --single-sided
```

`python build_model.py` is a root-level shortcut for the same generation step.

## Two-sided figures

By default every piece is a **two-sided figure**: the silhouette is fused with
its vertical mirror (base-to-base) so it reads upright from *both* edges of the
board — no piece is ever upside-down for either player, and the two sides are
told apart only by fill colour. This is controlled by the `two_sided` flag on
[`ChessStyle`](src/chess2d/parameters.py):

```python
from chess2d import ChessStyle, generate_all

generate_all(style=ChessStyle(two_sided=False))   # single-sided silhouettes
```

The same `two_sided_figure` flag is available directly on `make_piece`,
`make_piece_solid` and `make_piece_geometry`.

## Previewing

With the optional viewer installed (`uv sync --extra preview`):

```bash
python scripts/preview_set.py          # full board in ocp_vscode
python scripts/preview_set.py pieces   # the six silhouettes side by side
```

## Library usage

```python
from chess2d import make_piece, make_board, make_initial_position, PieceType

pawn   = make_piece(PieceType.PAWN)          # a Sketch face
board  = make_board()                         # light/dark square groups + border
scene  = make_initial_position()              # board + white/black piece layers
```

Piece generators are pure functions: they take a `scale` and return geometry,
never touching the filesystem or the viewer.

```python
from chess2d import make_piece_geometry, make_piece_solid

geom  = make_piece_geometry(PieceType.KNIGHT, with_solid=True)
# geom.fill (Sketch), geom.outline (Shape), geom.optional_solid (Part)

token = make_piece_solid(PieceType.QUEEN, thickness=2.0)   # flat 3D token
```

## Coordinate system & dimensions

* Units: millimetres. Board centred on the origin.
* X: left→right, Y: bottom→top (White at −Y, Black at +Y), Z: out of the board.
* Every piece is authored facing +Y with its local origin at its bounding-box
  centre; Black pieces are placed with a 180° rotation about Z.

Master dimensions live in [`src/chess2d/parameters.py`](src/chess2d/parameters.py)
(`SQUARE_SIZE = 50 mm`, `PLAYING_SIZE = 400 mm`, `BOARD_SIZE = 420 mm`, …) and are
bundled into a tunable [`ChessStyle`](src/chess2d/parameters.py) dataclass.

## Project layout

```
src/chess2d/
├── parameters.py   dimensions, enums (PieceType, Side), ChessStyle
├── geometry.py     low-level helpers (rounded_bar, symmetric, outline, scale)
├── pieces.py       the six make_* silhouette generators + dispatcher + solids
├── board.py        make_board, make_square, square_center, colour parity
├── assembly.py     place_piece, make_initial_position, BACK_RANK
└── preview.py      optional ocp_vscode helpers
scripts/            generate_all.py, preview_set.py
tests/              test_pieces.py, test_board.py, test_layout.py
```

## Development

```bash
uv run pytest        # 64 geometry / layout validation tests
uv run ruff check .  # lint
uv run mypy          # type-check src/chess2d
```

The tests assert the acceptance criteria: every piece resolves to a valid,
in-square face with closed wires; symmetric pieces are symmetric and the knight
is intentionally asymmetric; the board has exactly 32 light + 32 dark squares
with h1 light; and the opening has the correct 16 + 16 piece counts with Black
rotated consistently.
