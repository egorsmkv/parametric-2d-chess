"""The Hugging Face Space payload must stay complete and self-contained.

These run on every commit so a rename or a new module cannot silently break the
deployed Space.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "deploy_space.py"


def _load_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("deploy_space", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deploy_space = _load_module()


@pytest.fixture
def payload(tmp_path: Path) -> Path:
    return deploy_space.assemble(tmp_path / "space")


def test_payload_has_the_space_entrypoint_and_metadata(payload: Path) -> None:
    for name in ("app.py", "README.md", "requirements.txt"):
        assert (payload / name).is_file(), f"{name} missing from the Space payload"


def test_payload_bundles_the_package(payload: Path) -> None:
    package = payload / "chess2d"
    assert (package / "__init__.py").is_file()
    assert (package / "gradio_app.py").is_file()
    # Everything the app imports must ship with it.
    for module in ("assembly", "board", "export", "geometry", "parameters", "pieces"):
        assert (package / f"{module}.py").is_file(), f"chess2d/{module}.py missing"


def test_space_readme_declares_the_gradio_sdk(payload: Path) -> None:
    header = (payload / "README.md").read_text()
    assert header.startswith("---"), "Space README needs YAML frontmatter"
    assert "sdk: gradio" in header
    assert "app_file: app.py" in header


def test_space_gradio_pin_matches_the_readme(payload: Path) -> None:
    # A mismatch makes the Space build with a different gradio than we test.
    readme = (payload / "README.md").read_text()
    requirements = (payload / "requirements.txt").read_text()
    sdk_version = next(
        line.split(":", 1)[1].strip()
        for line in readme.splitlines()
        if line.startswith("sdk_version:")
    )
    assert f"gradio=={sdk_version}" in requirements


def test_payload_excludes_caches(payload: Path) -> None:
    assert not list(payload.rglob("__pycache__"))
    assert not list(payload.rglob("*.pyc"))


def test_payload_imports_without_the_source_tree(payload: Path) -> None:
    # The Space has no src/ on the path: the copied package must be enough.
    result = subprocess.run(
        [sys.executable, "-c", "import chess2d.gradio_app as m; print(m.__file__)"],
        cwd=payload,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert str(payload) in result.stdout


def test_dry_run_does_not_need_credentials(tmp_path: Path) -> None:
    # Also proves huggingface_hub is imported lazily: a dry run must work
    # without it installed and without a token.
    env = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--space-id", "dry/run",
            "--dry-run", "--staging", str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "Dry run" in result.stdout


def test_deploy_without_a_token_fails_clearly(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--space-id", "dry/run",
            "--staging", str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0
    assert "no token" in result.stderr.lower()
