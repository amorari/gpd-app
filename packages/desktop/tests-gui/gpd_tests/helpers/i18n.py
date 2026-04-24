"""Access the committed GPD i18n dictionary snapshot."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DICT_PATH = Path(__file__).parent.parent / "fixtures" / "en.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, str]:
    # Explicit UTF-8: en.json is written as UTF-8 and may gain non-ASCII
    # strings over time (apostrophes, smart quotes, accented characters
    # in product copy). The default encoding would be the process locale,
    # which is UTF-8 on modern macOS/Linux but not guaranteed on Windows
    # CI runners or containers with the C locale.
    with _DICT_PATH.open(encoding="utf-8") as f:
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
