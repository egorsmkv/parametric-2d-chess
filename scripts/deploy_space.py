#!/usr/bin/env python
"""Deploy the Gradio app to a Hugging Face Space.

Assembles a Space payload -- the entrypoint, Dockerfile and metadata from
``space/`` plus a copy of the ``chess2d`` package -- and uploads it with
``huggingface_hub``. The Space is a Docker Space: the image carries Bambu Studio
so the app can slice a plate, which the plain gradio SDK cannot do.

Usage::

    python scripts/deploy_space.py --space-id owner/name        # deploy
    python scripts/deploy_space.py --space-id owner/name --dry-run

``--dry-run`` assembles and lists the payload without contacting the Hub, so the
packaging can be verified without credentials. Authentication otherwise comes
from ``$HF_TOKEN`` (or ``--token``).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPACE_DIR = ROOT / "space"
PACKAGE_DIR = ROOT / "src" / "chess2d"

# Remote files under our control; stale ones are pruned so a renamed or deleted
# module cannot linger in the Space and shadow the new code.
MANAGED_PATTERNS = [
    "*.py",
    "Dockerfile",
    "chess2d/*",
    # One level deeper: the style modules live in a subpackage, and a stale
    # copy left behind there would shadow the new code.
    "chess2d/styles/*",
    "requirements.txt",
    "README.md",
]

# Never ship caches or the optional viewer glue (ocp_vscode is not installed).
EXCLUDE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def assemble(staging: Path) -> Path:
    """Build the Space payload in ``staging``. Returns the payload directory."""
    if not SPACE_DIR.is_dir():
        raise SystemExit(f"missing Space template directory: {SPACE_DIR}")

    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    # 1. Space metadata + entrypoint (README.md carries the HF frontmatter).
    shutil.copytree(SPACE_DIR, staging, dirs_exist_ok=True, ignore=EXCLUDE)
    # 2. The package itself, importable as `chess2d` from the Space root.
    shutil.copytree(PACKAGE_DIR, staging / "chess2d", ignore=EXCLUDE)
    return staging


def _payload_files(staging: Path) -> list[Path]:
    return sorted(p for p in staging.rglob("*") if p.is_file())


def deploy(space_id: str, staging: Path, token: str) -> str:
    """Upload the assembled payload to the Space. Returns the Space URL."""
    from huggingface_hub import HfApi  # noqa: PLC0415

    api = HfApi(token=token)
    # Idempotent: creates the Space on the first run, no-op afterwards.
    # Docker rather than the gradio SDK: the image also carries Bambu Studio,
    # which is what lets the Space slice a plate for the printer.
    api.create_repo(
        repo_id=space_id,
        repo_type="space",
        space_sdk="docker",
        exist_ok=True,
    )
    api.upload_folder(
        repo_id=space_id,
        repo_type="space",
        folder_path=str(staging),
        delete_patterns=MANAGED_PATTERNS,
        commit_message=os.environ.get("SPACE_COMMIT_MESSAGE", "Deploy from CI"),
    )
    return f"https://huggingface.co/spaces/{space_id}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space-id", required=True, help="target Space, as owner/name")
    parser.add_argument("--token", default=os.environ.get("HF_TOKEN", ""))
    parser.add_argument("--staging", type=Path, default=ROOT / "build" / "space")
    parser.add_argument(
        "--dry-run", action="store_true", help="assemble only; do not contact the Hub",
    )
    args = parser.parse_args(argv)

    staging = assemble(args.staging)
    files = _payload_files(staging)
    total = sum(f.stat().st_size for f in files)
    print(f"Assembled {len(files)} files ({total / 1e3:.0f} kB) in {staging}:")
    for path in files:
        print(f"  {path.relative_to(staging)}")

    # Fail fast on an incomplete payload rather than publishing a broken Space.
    required = {Path("app.py"), Path("README.md"), Path("requirements.txt"), Path("Dockerfile")}
    present = {f.relative_to(staging) for f in files}
    if missing := required - present:
        raise SystemExit(f"payload is missing: {', '.join(str(m) for m in sorted(missing))}")
    if not (staging / "chess2d" / "gradio_app.py").is_file():
        raise SystemExit("payload is missing chess2d/gradio_app.py")

    if args.dry_run:
        print("\nDry run: nothing uploaded.")
        return 0
    if not args.token:
        raise SystemExit("no token: set $HF_TOKEN or pass --token")

    url = deploy(args.space_id, staging, args.token)
    print(f"\nDeployed to {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
