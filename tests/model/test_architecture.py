"""Enforce documented import layer ordering.

Layer order (lower index = lower layer, must not import higher layers):
  protocol < media < playback < topology < events < aggregates < registry
"""
from __future__ import annotations

import ast
import pathlib

MODEL_DIR = pathlib.Path("src/cprima_raumtube/model")

LAYER_ORDER = ["protocol", "media", "playback", "topology", "events", "aggregates", "registry"]
_rank = {name: i for i, name in enumerate(LAYER_ORDER)}


def _imports_from_model(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    deps = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "cprima_raumtube.model." in node.module:
                dep = node.module.split(".")[-1]
                if dep in _rank:
                    deps.append(dep)
    return deps


def test_no_upward_imports() -> None:
    """No model module may import from a higher layer."""
    violations = []
    for py in sorted(MODEL_DIR.glob("*.py")):
        mod = py.stem
        if mod not in _rank or mod == "__init__":
            continue
        for dep in _imports_from_model(py):
            if _rank[dep] >= _rank[mod]:
                violations.append(f"{mod} (rank {_rank[mod]}) imports {dep} (rank {_rank[dep]})")
    assert not violations, "Layer ordering violations:\n" + "\n".join(violations)


def test_ids_has_no_model_imports() -> None:
    """ids.py must not import from any other model module (it is a leaf)."""
    ids_path = MODEL_DIR / "ids.py"
    if not ids_path.exists():
        return
    deps = _imports_from_model(ids_path)
    assert not deps, f"ids.py must not import from model: {deps}"


def test_protocol_has_no_model_imports() -> None:
    """protocol.py is the lowest layer — it must not import from other model modules."""
    deps = _imports_from_model(MODEL_DIR / "protocol.py")
    assert not deps, f"protocol.py must not import from model: {deps}"
