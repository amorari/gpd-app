"""On-failure artifact capture helpers."""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_ROOT = Path("artifacts")


def artifact_dir(module: str, test: str, *, root: Path = DEFAULT_ROOT) -> Path:
    """Return artifacts/<module>/<test>/, creating it."""
    d = root / module / test
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(dir_: Path, name: str, data: object) -> Path:
    p = dir_ / name
    p.write_text(json.dumps(data, indent=2, default=str))
    return p


def save_text(dir_: Path, name: str, text: str) -> Path:
    p = dir_ / name
    p.write_text(text)
    return p


def save_bytes(dir_: Path, name: str, data: bytes) -> Path:
    p = dir_ / name
    p.write_bytes(data)
    return p
