"""On-failure artifact capture helpers."""
from __future__ import annotations

import json
import time
from pathlib import Path

# Absolute path to <tests-gui>/artifacts/, regardless of the pytest invocation CWD.
DEFAULT_ROOT = Path(__file__).resolve().parent.parent.parent / "artifacts"


def artifact_dir(module: str, test: str, *, root: Path = DEFAULT_ROOT) -> Path:
    """Return ``<root>/<module>/<test>/``, creating it.

    If the directory already exists and contains files from a previous run
    (e.g. a parametrize collision), a timestamp suffix is appended to avoid
    silently overwriting earlier artifacts.
    """
    d = root / module / test
    if d.exists() and any(d.iterdir()):
        # Collision: differentiate with a compact UTC timestamp.
        suffix = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        d = root / module / f"{test}__{suffix}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(dir_: Path, name: str, data: object) -> Path:
    p = dir_ / name
    p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return p


def save_text(dir_: Path, name: str, text: str) -> Path:
    p = dir_ / name
    p.write_text(text, encoding="utf-8")
    return p


def save_bytes(dir_: Path, name: str, data: bytes) -> Path:
    p = dir_ / name
    p.write_bytes(data)
    return p
