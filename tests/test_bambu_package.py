"""Guards on the shape of the :mod:`chess2d.bambu` package itself.

``bambu`` was one module before it was four, and callers still import every
name straight off the package. These tests fail if a name is dropped on the way
out of a submodule, or if the geometry/installation split stops holding.
"""

from __future__ import annotations

from pathlib import Path

from chess2d import bambu
from chess2d.bambu import plate, printers, profiles, slicing

SUBMODULES = (printers, plate, profiles, slicing)


def test_the_facade_re_exports_exactly_what_the_submodules_export() -> None:
    from_submodules = {name for module in SUBMODULES for name in module.__all__}
    assert set(bambu.__all__) == from_submodules


def test_every_exported_name_actually_resolves() -> None:
    missing = [name for name in bambu.__all__ if not hasattr(bambu, name)]
    assert not missing, f"declared in __all__ but not importable: {missing}"


def test_only_the_plate_module_needs_build123d() -> None:
    # The point of the split: profile discovery and the CLI wrapper stay
    # stdlib-only, so they can be imported without paying for the CAD kernel.
    heavy = [
        module.__name__
        for module in (printers, profiles, slicing)
        if "build123d" in Path(module.__file__ or "").read_text(encoding="utf-8")
    ]
    assert not heavy, f"these should not depend on build123d: {heavy}"


def test_the_base_module_depends_on_no_sibling() -> None:
    # printers.py is what lets the two halves avoid importing each other.
    source = Path(printers.__file__ or "").read_text(encoding="utf-8")
    assert "from ." not in source
    assert "import ." not in source
