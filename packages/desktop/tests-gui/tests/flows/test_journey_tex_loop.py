"""G6.4 — TeX compile-edit-recompile journey.

End-to-end user journey against the live Tauri commands exposed by
``packages/desktop/src-tauri/src/tex_compiler.rs``:

    1. Stage a ``.tex`` source under ``tmp_path``.
    2. ``compile_tex`` → capture PDF bytes (``pdf_a``) and log path (``log_a``).
    3. ``parse_tex_log`` on ``log_a`` → assert no errors for a well-formed input.
    4. Edit the source (add a visible sentence).
    5. ``compile_tex`` again → capture PDF bytes (``pdf_b``).
    6. Assert ``pdf_b != pdf_a`` — the compiler's output is content-dependent,
       so adding a real sentence must change the PDF bytes.

Skips when no TeX compiler is installed on the host (matches the
``no_compiler`` contract surfaced by ``compile_tex``).

All fixtures live in ``tmp_path``; the only GPD-owned directory we touch is
the ``.tex-builds`` cache via the read-artifact command (which is itself
created by the compile).
"""
from __future__ import annotations

import base64
import shutil
from pathlib import Path

import pytest

from gpd_tests.helpers.ipc import invoke_via_mcp


# A minimal-but-real article. Keeping the preamble tiny lets a cold
# ``tectonic`` finish under the 120s timeout.
INITIAL_TEX = (
    r"\documentclass{article}" "\n"
    r"\begin{document}" "\n"
    r"Hello from G6.4 journey test." "\n"
    r"\end{document}" "\n"
)


# The edit we apply between compiles. Adding a visible paragraph changes the
# typeset output (glyph stream + page content), so ``pdf_b != pdf_a``.
EDITED_TEX = (
    r"\documentclass{article}" "\n"
    r"\begin{document}" "\n"
    r"Hello from G6.4 journey test." "\n"
    r"A second paragraph was added to force a different PDF byte stream." "\n"
    r"\end{document}" "\n"
)


def _has_tex_compiler() -> bool:
    """Mirror the Rust ``resolve_tex_compiler`` order at a coarse level.

    We don't poke the Tauri command here — we just check PATH so the test
    can skip up front with a clear message rather than short-circuit on the
    ``no_compiler`` contract mid-flow.
    """
    return (
        shutil.which("pdflatex") is not None
        or shutil.which("tectonic") is not None
    )


@pytest.mark.flows
@pytest.mark.ipc
@pytest.mark.timeout(240)
def test_journey_tex_loop(mcp, tmp_path):
    """Compile → log → edit → recompile → assert output changed."""
    if not _has_tex_compiler():
        pytest.skip(
            "no TeX compiler on host (pdflatex/tectonic) — "
            "G6.4 journey exercises the full compile loop"
        )

    tex = tmp_path / "journey.tex"
    tex.write_text(INITIAL_TEX)

    # --- Compile #1 ---------------------------------------------------------
    first = invoke_via_mcp(
        mcp,
        "compile_tex",
        {
            "projectId": "gpd-g64-journey",
            "texFile": str(tex),
            "rootFile": None,
        },
    )
    assert isinstance(first, dict), f"compile_tex must return a dict: {first!r}"

    status_a = first.get("status")
    if status_a == "no_compiler":
        # Race: compiler vanished between PATH check and invoke. Treat as skip.
        pytest.skip("compiler unavailable at invoke time; skipping")

    assert status_a in {"success", "success_with_warnings"}, (
        f"INITIAL_TEX should compile cleanly on a compiler-equipped host; "
        f"got status={status_a!r}, result={first!r}"
    )

    pdf_a_path = first.get("pdfPath")
    log_a_path = first.get("logPath")
    assert pdf_a_path, f"expected pdfPath from first compile: {first!r}"
    assert log_a_path, f"expected logPath from first compile: {first!r}"
    assert Path(pdf_a_path).is_file(), f"pdfPath does not exist: {pdf_a_path!r}"
    assert Path(log_a_path).is_file(), f"logPath does not exist: {log_a_path!r}"

    # Read the PDF bytes through the sandboxed artifact reader — this is the
    # same path the UI uses and it enforces the cache-containment guard.
    pdf_a_b64 = invoke_via_mcp(
        mcp, "read_tex_artifact_base64", {"path": pdf_a_path}
    )
    assert isinstance(pdf_a_b64, str) and pdf_a_b64, (
        f"empty base64 for first PDF: {pdf_a_b64!r}"
    )
    pdf_a_bytes = base64.b64decode(pdf_a_b64)
    assert pdf_a_bytes.startswith(b"%PDF-"), (
        f"first artifact is not a PDF: {pdf_a_bytes[:16]!r}"
    )

    # --- parse_tex_log: log for a clean source must have no errors ----------
    parsed = invoke_via_mcp(mcp, "parse_tex_log", {"logPath": log_a_path})
    assert isinstance(parsed, dict)
    assert isinstance(parsed.get("errors"), list)
    assert parsed["errors"] == [], (
        f"clean compile should have no parsed errors; got {parsed['errors']!r}"
    )
    # ``warnings`` is allowed to be non-empty (font substitution etc. are
    # common on a fresh install) — the no-error assertion is the contract.

    # --- Edit the source ----------------------------------------------------
    tex.write_text(EDITED_TEX)

    # --- Compile #2 ---------------------------------------------------------
    second = invoke_via_mcp(
        mcp,
        "compile_tex",
        {
            "projectId": "gpd-g64-journey",
            "texFile": str(tex),
            "rootFile": None,
        },
    )
    assert isinstance(second, dict), (
        f"compile_tex must return a dict on recompile: {second!r}"
    )
    status_b = second.get("status")
    if status_b == "no_compiler":
        pytest.skip("compiler vanished between compile #1 and compile #2")
    assert status_b in {"success", "success_with_warnings"}, (
        f"EDITED_TEX should still compile cleanly; got status={status_b!r}, "
        f"result={second!r}"
    )

    pdf_b_path = second.get("pdfPath")
    assert pdf_b_path, f"expected pdfPath from second compile: {second!r}"
    assert Path(pdf_b_path).is_file(), f"pdfPath does not exist: {pdf_b_path!r}"

    pdf_b_b64 = invoke_via_mcp(
        mcp, "read_tex_artifact_base64", {"path": pdf_b_path}
    )
    assert isinstance(pdf_b_b64, str) and pdf_b_b64
    pdf_b_bytes = base64.b64decode(pdf_b_b64)
    assert pdf_b_bytes.startswith(b"%PDF-"), (
        f"second artifact is not a PDF: {pdf_b_bytes[:16]!r}"
    )

    # --- Content-dependent output: adding a sentence must change the PDF ----
    # PDFs embed metadata (creation time, mod date, /ID entries) that typically
    # drift even for identical sources, but we want a *content-dependent*
    # signal. The stronger assertion we can make portably is bytes-differ —
    # that holds whether or not the compiler stamps a timestamp, because the
    # glyph stream and page content objects also change.
    assert pdf_b_bytes != pdf_a_bytes, (
        "second PDF has identical bytes to the first after editing the source — "
        "the compiler is either caching output or not re-reading the .tex file"
    )
