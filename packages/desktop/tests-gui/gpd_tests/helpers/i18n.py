"""Access the committed GPD i18n dictionary snapshot."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DICT_PATH = Path(__file__).parent.parent / "fixtures" / "en.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, str]:
    with _DICT_PATH.open() as f:
        return json.load(f)


def t(key: str) -> str:
    """Return the English string for an i18n key. Raise KeyError if absent."""
    d = _load()
    if key not in d:
        raise KeyError(f"i18n key not found: {key}")
    return d[key]


def all_keys() -> list[str]:
    """Return all i18n keys, sorted."""
    return sorted(_load().keys())
