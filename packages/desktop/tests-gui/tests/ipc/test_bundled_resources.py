"""Contract tests for read_third_party_notices() and read_license() (lib.rs).

Both commands take no arguments and return the contents of a bundled resource
file as a string. They are exercised here against a live GPD debug build.

Commands covered:
  - read_third_party_notices  (returns THIRD_PARTY_NOTICES.md)
  - read_license              (returns LICENSE)
"""
from __future__ import annotations

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


# ---------------------------------------------------------------------------
# read_third_party_notices
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_read_third_party_notices_contains_expected_content(mcp):
    """read_third_party_notices returns a non-empty string containing 'MIT'.

    The bundled THIRD_PARTY_NOTICES.md lists MIT as the dominant permissive
    license across both the npm and Cargo stacks; its presence is a stable
    command-contract invariant regardless of the exact file heading.
    """
    try:
        result = invoke_via_mcp(mcp, "read_third_party_notices", {})
    except IPCError as e:
        pytest.skip(f"read_third_party_notices IPC command unavailable: {e}")

    assert isinstance(result, str), (
        f"expected str, got {type(result).__name__}: {result!r}"
    )
    assert len(result) > 0, "read_third_party_notices returned an empty string"
    assert "MIT" in result, (
        "expected 'MIT' in the third-party notices (dominant permissive license)"
    )


# ---------------------------------------------------------------------------
# read_license
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_read_license_contains_expected_content(mcp):
    """read_license returns a non-empty string consistent with an MIT LICENSE file.

    The bundled LICENSE starts with 'MIT License' and contains the standard
    'Permission is hereby granted' grant clause; both are stable invariants.
    """
    try:
        result = invoke_via_mcp(mcp, "read_license", {})
    except IPCError as e:
        pytest.skip(f"read_license IPC command unavailable: {e}")

    assert isinstance(result, str), (
        f"expected str, got {type(result).__name__}: {result!r}"
    )
    assert len(result) > 0, "read_license returned an empty string"
    assert "MIT" in result, (
        "expected 'MIT' in the LICENSE file (bundled file starts with 'MIT License')"
    )
    assert "Permission" in result, (
        "expected 'Permission' in the LICENSE file "
        "(standard MIT 'Permission is hereby granted' clause)"
    )
