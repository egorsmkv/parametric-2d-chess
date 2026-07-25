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

from chess2d import bambu

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
    for name in ("app.py", "README.md", "requirements.txt", "Dockerfile"):
        assert (payload / name).is_file(), f"{name} missing from the Space payload"


def test_payload_bundles_the_package(payload: Path) -> None:
    package = payload / "chess2d"
    assert (package / "__init__.py").is_file()
    assert (package / "gradio_app.py").is_file()
    # Everything the app imports must ship with it.
    for module in (
        "assembly", "bambu", "board", "estimate", "export", "geometry",
        "parameters", "pieces", "report",
    ):
        assert (package / f"{module}.py").is_file(), f"chess2d/{module}.py missing"

    # The piece styles live in a subpackage; copytree must have recursed into it.
    styles = package / "styles"
    assert (styles / "__init__.py").is_file(), "chess2d/styles/ missing from payload"
    for style in (
        "staunton", "regence", "selenus", "st_george", "edinburgh",
        "bauhaus", "man_ray", "glyph", "lewis",
    ):
        assert (styles / f"{style}.py").is_file(), f"chess2d/styles/{style}.py missing"


def test_space_readme_declares_the_docker_sdk(payload: Path) -> None:
    header = (payload / "README.md").read_text(encoding="utf-8")
    assert header.startswith("---"), "Space README needs YAML frontmatter"
    assert "sdk: docker" in header
    # Without app_port the Space has no idea which port to route to.
    assert "app_port: 7860" in header
    # Leftovers from the gradio SDK: sdk_version would contradict `sdk: docker`,
    # and app_file only means anything to the SDK Spaces (the Dockerfile's CMD
    # is the entrypoint here).
    assert "sdk_version:" not in header
    assert "app_file:" not in header


def test_the_dockerfile_serves_the_app_where_the_space_expects_it(payload: Path) -> None:
    dockerfile = (payload / "Dockerfile").read_text(encoding="utf-8")
    assert "GRADIO_SERVER_NAME=0.0.0.0" in dockerfile, "must bind outside the container"
    assert "GRADIO_SERVER_PORT=7860" in dockerfile
    assert "EXPOSE 7860" in dockerfile
    assert 'CMD ["python", "app.py"]' in dockerfile


def test_the_dockerfile_installs_bambu_studio_where_chess2d_looks(payload: Path) -> None:
    # The whole point of the Docker Space: slicing has to be available. These
    # are the two hooks chess2d.bambu reads, so a rename here must fail loudly.
    dockerfile = (payload / "Dockerfile").read_text(encoding="utf-8")
    assert f"{bambu.EXECUTABLE_ENV}=" in dockerfile
    assert f"{bambu.PROFILES_ENV}=" in dockerfile
    assert "--appimage-extract" in dockerfile, "AppImages need FUSE unless extracted"
    assert "xvfb" in dockerfile, "the Bambu Studio CLI still needs a display"


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
