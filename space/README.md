---
title: 2D Chess Set Generator
emoji: ♟️
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 2D Chess Set Generator

Parametric 2D chessboard and flat chess-piece silhouettes, generated with
[build123d](https://build123d.readthedocs.io).

Pick a figure form and the board / figure sizes, watch the starting position
update live, then download the whole set as **SVG, DXF, STEP, STL and 3MF** —
ready for laser cutting, plotting or 3D printing.

* **Figure form** — two-sided (each player reads their own end), fused
  (point-symmetric, reads the same for everyone) or single-sided.
* **Board size** — 35 / 50 / 65 mm squares (280 / 400 / 520 mm board).
* **Figure size** — how much of a square each piece fills.
* **Bambu Lab plate** — the pieces laid out on a build plate as a 3MF, with the
  packed size checked against the printer you choose. Bambu Studio is installed
  in this Space's image, so ticking **Slice with Bambu Studio** returns a
  printer-ready `.gcode.3mf`; leave it unticked for a generic 3MF to slice
  yourself.

Source: <https://github.com/egorsmkv/parametric-2d-chess>

> This Space is deployed automatically from `main` after the test suite passes.
> Files here are generated — edit the source repository instead.
