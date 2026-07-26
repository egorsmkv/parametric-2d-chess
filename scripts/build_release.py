#!/usr/bin/env python
"""Build release artifacts: model archives (STEP/STL/SVG/DXF) + rendered board images.

One archive and one board image are produced per :class:`FigureMode`, so a
release ships the full model set alongside a picture of the board it produces.

Usage::

    python scripts/build_release.py --version v1.0.0 [--dist dist] [--no-images]

Rasterising the board needs one of ``cairosvg`` (pip), ``rsvg-convert``
(``librsvg2-bin``) or ``inkscape``; pass ``--no-images`` to skip it.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Allow running directly from a source checkout without installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chess2d.export import generate_all
from chess2d.parameters import ChessStyle, FigureMode

IMAGE_WIDTH = 1400


def render_png(svg: Path, png: Path, width: int = IMAGE_WIDTH) -> str:
    """Rasterise ``svg`` to ``png``; returns the backend used.

    Raises ``RuntimeError`` when no rasteriser is available so CI fails loudly
    rather than publishing a release with missing images.
    """
    png.parent.mkdir(parents=True, exist_ok=True)

    try:
        import cairosvg  # noqa: PLC0415

        cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=width)
        return "cairosvg"
    except Exception:  # noqa: BLE001, S110
        # Not just ImportError: cairosvg imports fine but raises OSError when the
        # system libcairo is missing, so fall through to the CLI rasterisers.
        pass

    candidates = (
        ("rsvg-convert", ["rsvg-convert", "-w", str(width), "-o", str(png), str(svg)]),
        (
            "inkscape",
            [
                "inkscape",
                str(svg),
                "--export-type=png",
                f"--export-width={width}",
                f"--export-filename={png}",
            ],
        ),
    )
    for tool, command in candidates:
        if shutil.which(tool):
            subprocess.run(command, check=True, capture_output=True)
            return tool

    raise RuntimeError(
        "No SVG rasteriser found. Install one of: cairosvg (pip install cairosvg), "
        "librsvg2-bin (rsvg-convert), or inkscape -- or pass --no-images.",
    )


def _check_archive_contents(out_dir: Path, mode: FigureMode) -> None:
    """Fail early if the generated tree is missing its STEP/STL models."""
    step_files = sorted((out_dir / "step").glob("*.step"))
    stl_files = sorted((out_dir / "stl").glob("*.stl"))
    if not step_files:
        raise RuntimeError(f"{mode.value}: no STEP files were generated")
    if not stl_files:
        raise RuntimeError(f"{mode.value}: no STL files were generated")


def build(version: str, dist: Path, with_images: bool = True) -> list[Path]:
    """Generate every artifact for a release. Returns the asset paths."""
    shutil.rmtree(dist, ignore_errors=True)
    dist.mkdir(parents=True, exist_ok=True)
    staging = dist / "_build"

    assets: list[Path] = []
    for mode in FigureMode:
        out_dir = staging / mode.value
        print(f"[{mode.value}] generating models ...")
        generate_all(
            output_dir=out_dir,
            style=ChessStyle(figure_mode=mode),
            with_solids=True,
        )
        _check_archive_contents(out_dir, mode)

        archive = shutil.make_archive(str(dist / f"chess2d-{mode.value}-{version}"), "zip", out_dir)
        assets.append(Path(archive))
        print(f"[{mode.value}] archive  -> {Path(archive).name}")

        if with_images:
            png = dist / f"board-{mode.value}-{version}.png"
            backend = render_png(out_dir / "svg" / "initial_position.svg", png)
            assets.append(png)
            print(f"[{mode.value}] image    -> {png.name} (via {backend})")

    # Drop the intermediate tree so `dist/*` contains only release assets.
    shutil.rmtree(staging, ignore_errors=True)
    return assets


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="dev", help="version/tag label for filenames")
    parser.add_argument("--dist", default="dist", type=Path, help="output directory")
    parser.add_argument(
        "--no-images", action="store_true", help="skip rasterising the board previews",
    )
    args = parser.parse_args(argv)

    assets = build(args.version, args.dist, with_images=not args.no_images)
    total = sum(a.stat().st_size for a in assets)
    print(f"\n{len(assets)} assets in {args.dist}/ ({total / 1e6:.1f} MB):")
    for asset in assets:
        print(f"  {asset.name:44s} {asset.stat().st_size / 1e6:6.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
