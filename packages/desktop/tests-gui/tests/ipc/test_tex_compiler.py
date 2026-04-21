"""Contract tests for tex_compiler.rs Tauri commands.

Covers the 7 commands exposed in ``packages/desktop/src-tauri/src/tex_compiler.rs``:

    detect_tex_root, detect_tex_compiler, compile_tex,
    synctex_forward, synctex_reverse, read_tex_artifact_base64, parse_tex_log

Happy-path + (where meaningful) a failure-mode test per command. Tests are
realistic about environment: if no TeX compiler is installed on the host,
``compile_tex`` returns a well-formed result with ``status == "no_compiler"``
rather than raising — we assert on the structured shape either way. When
``synctex`` is missing the two SyncTeX commands raise IPCError; we test both
the missing-binary and (when present) successful-lookup paths.

All tests run against the live GPD debug build through MCP (``@pytest.mark.ipc``).
We never create TeX fixtures on disk outside ``tmp_path``.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


# Keep inputs tiny so a cold ``tectonic`` still fits under the 120s timeout.
# Single line, no packages beyond ``article``, no bibliography.
TINY_TEX = (
    r"\documentclass{article}"
    r"\begin{document}Hello from GPD contract tests.\end{document}"
)


# A .tex file with a magic-comment root pointer. The root-detection logic
# strips ``% !TEX root = <path>`` from the first few lines.
TEX_WITH_MAGIC_ROOT_TEMPLATE = (
    "% !TEX root = {root}\n"
    r"\input{stub}"
)


def _has_tex_compiler() -> bool:
    """Best-effort: is a TeX compiler likely resolvable on this host?

    Mirrors the Rust ``resolve_tex_compiler`` resolution order at a coarse
    level — we don't import Rust here, we just look on PATH.
    """
    return (
        shutil.which("pdflatex") is not None
        or shutil.which("tectonic") is not None
    )


def _has_synctex() -> bool:
    return shutil.which("synctex") is not None


# ---------------------------------------------------------------------------
# detect_tex_root
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_detect_tex_root_falls_back_to_start_file(mcp, tmp_path):
    """No magic comment, no .latexmkrc, no sibling with \\documentclass —
    detect_tex_root must return the input path unchanged (case 4 fallback)."""
    tex = tmp_path / "solo.tex"
    tex.write_text("just some text, no documentclass, no magic root\n")

    result = invoke_via_mcp(mcp, "detect_tex_root", {"startFile": str(tex)})

    assert isinstance(result, str)
    assert result == str(tex)


@pytest.mark.ipc
def test_detect_tex_root_honors_magic_comment(mcp, tmp_path):
    """A ``% !TEX root = …`` magic comment at the top of the start file
    redirects to the referenced root (when that root exists)."""
    root = tmp_path / "main.tex"
    root.write_text(TINY_TEX)

    child = tmp_path / "chapter.tex"
    child.write_text(
        TEX_WITH_MAGIC_ROOT_TEMPLATE.format(root=root.name)
    )

    result = invoke_via_mcp(mcp, "detect_tex_root", {"startFile": str(child)})

    assert isinstance(result, str)
    # The Rust side resolves relative roots against the start-file's parent,
    # so the returned path must point at ``main.tex``.
    assert Path(result).resolve() == root.resolve()


# ---------------------------------------------------------------------------
# detect_tex_compiler
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_detect_tex_compiler_returns_well_formed_info(mcp):
    """detect_tex_compiler always returns a ``TexCompilerInfo`` shape — even
    when nothing is installed (``kind == "none"``). We don't assume the host
    has pdflatex/tectonic, just that the contract is respected."""
    info = invoke_via_mcp(mcp, "detect_tex_compiler", {})

    assert isinstance(info, dict)
    # ``kind`` is serialized verbatim as a string — "pdflatex" | "tectonic" | "none".
    assert info.get("kind") in {"pdflatex", "tectonic", "none"}
    # camelCase per ``#[serde(rename_all = "camelCase")]``.
    for key in ("hasLatexmk", "hasBibtex", "hasSynctex"):
        assert key in info, f"missing boolean field {key!r} in {info!r}"
        assert isinstance(info[key], bool)
    # ``path`` is ``None`` iff ``kind == "none"``.
    if info["kind"] == "none":
        assert info.get("path") in (None, "")
    else:
        assert isinstance(info.get("path"), str) and info["path"]


# ---------------------------------------------------------------------------
# compile_tex
# ---------------------------------------------------------------------------


@pytest.mark.ipc
@pytest.mark.timeout(120)
def test_compile_tex_happy_path(mcp, tmp_path):
    """compile_tex returns a structured result. On hosts with a compiler we
    expect ``status == "success"``; on bare hosts we expect ``"no_compiler"``.
    Either way the result must be a well-formed dict."""
    tex = tmp_path / "tiny.tex"
    tex.write_text(TINY_TEX)

    result = invoke_via_mcp(
        mcp,
        "compile_tex",
        {
            "projectId": "gpd-contract-tests",
            "texFile": str(tex),
            "rootFile": None,
        },
    )

    assert isinstance(result, dict)
    assert result.get("status") in {
        "success",
        "success_with_warnings",
        "error",
        "no_compiler",
        "cancelled",
    }
    # duration is always reported.
    assert isinstance(result.get("durationMs"), (int, float))
    assert result["durationMs"] >= 0
    # ``rootFile`` echoes back the resolved root.
    assert result.get("rootFile") == str(tex)

    if result["status"] == "no_compiler":
        # With no compiler the heavy fields are None/empty.
        assert result.get("pdfPath") in (None, "")
        assert result.get("compilerKind") in (None, "")
        pytest.skip("no TeX compiler on host — skipping artifact checks")

    # Compiler ran — we expect a PDF path on success.
    if result["status"] in ("success", "success_with_warnings"):
        assert result.get("pdfPath"), f"no pdfPath on {result['status']}"
        assert Path(result["pdfPath"]).is_file()


@pytest.mark.ipc
def test_compile_tex_rejects_missing_source(mcp, tmp_path):
    """When the supplied root path doesn't exist, compile_tex must fail up
    front (before even checking for a compiler) with a clear Err string."""
    nonexistent = tmp_path / "does-not-exist.tex"
    with pytest.raises(IPCError, match="(?i)not found|doesn't exist|hasn't been moved"):
        invoke_via_mcp(
            mcp,
            "compile_tex",
            {
                "projectId": "gpd-contract-tests",
                "texFile": str(nonexistent),
                "rootFile": str(nonexistent),
            },
        )


# ---------------------------------------------------------------------------
# synctex_forward / synctex_reverse
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_synctex_forward_contract(mcp, tmp_path):
    """Forward lookup: if ``synctex`` CLI is missing we must see an IPCError
    mentioning it; if present with a bogus .synctex.gz path the command either
    errors or returns a ``SyncTexResult`` with None fields. Either behavior is
    a valid contract — we just guarantee we don't silently return garbage."""
    fake_synctex = tmp_path / "nope.synctex.gz"
    fake_synctex.write_bytes(b"not a real synctex file")

    if not _has_synctex():
        with pytest.raises(IPCError, match="(?i)synctex"):
            invoke_via_mcp(
                mcp,
                "synctex_forward",
                {"synctexPath": str(fake_synctex), "page": 1, "x": 0.0, "y": 0.0},
            )
        return

    # ``synctex`` is installed — the CLI will run but reject the fake file.
    # The Rust layer reads stdout and returns an empty SyncTexResult rather
    # than an error, so we accept either "IPCError" or "None-filled result".
    try:
        result = invoke_via_mcp(
            mcp,
            "synctex_forward",
            {"synctexPath": str(fake_synctex), "page": 1, "x": 0.0, "y": 0.0},
        )
    except IPCError:
        return
    assert isinstance(result, dict)
    # All fields declared ``Option<_>`` → JSON ``None`` for an unparseable input.
    assert result.get("file") in (None, "")
    assert result.get("line") in (None, 0)


@pytest.mark.ipc
def test_synctex_reverse_contract(mcp, tmp_path):
    """Reverse lookup: mirror of ``synctex_forward``'s contract."""
    fake_synctex = tmp_path / "nope.synctex.gz"
    fake_synctex.write_bytes(b"not a real synctex file")
    fake_source = tmp_path / "source.tex"
    fake_source.write_text(TINY_TEX)

    if not _has_synctex():
        with pytest.raises(IPCError, match="(?i)synctex"):
            invoke_via_mcp(
                mcp,
                "synctex_reverse",
                {
                    "synctexPath": str(fake_synctex),
                    "sourceFile": str(fake_source),
                    "line": 1,
                },
            )
        return

    try:
        result = invoke_via_mcp(
            mcp,
            "synctex_reverse",
            {
                "synctexPath": str(fake_synctex),
                "sourceFile": str(fake_source),
                "line": 1,
            },
        )
    except IPCError:
        return
    assert isinstance(result, dict)
    assert result.get("page") in (None, 0)
    assert result.get("x") in (None, 0, 0.0)
    assert result.get("y") in (None, 0, 0.0)


# ---------------------------------------------------------------------------
# read_tex_artifact_base64
# ---------------------------------------------------------------------------


@pytest.mark.ipc
@pytest.mark.timeout(120)
def test_read_tex_artifact_base64_happy_path(mcp, tmp_path):
    """Chain: compile → read_tex_artifact_base64(log path).

    The log file is the most reliable artifact — it's produced by every
    successful and most failed compiles, and it's guaranteed to live under the
    ``.tex-builds`` cache dir (the only location the command allows reads from)."""
    if not _has_tex_compiler():
        pytest.skip("no TeX compiler on host — can't produce an artifact to read")

    tex = tmp_path / "tiny.tex"
    tex.write_text(TINY_TEX)

    compile_result = invoke_via_mcp(
        mcp,
        "compile_tex",
        {
            "projectId": "gpd-contract-tests",
            "texFile": str(tex),
            "rootFile": None,
        },
    )
    log_path = compile_result.get("logPath")
    if not log_path:
        pytest.skip(
            f"compile produced no log to read "
            f"(status={compile_result.get('status')!r}); skipping"
        )

    b64 = invoke_via_mcp(mcp, "read_tex_artifact_base64", {"path": log_path})

    assert isinstance(b64, str) and b64, "expected non-empty base64 string"
    # Alphabet sanity: only base64 chars + padding.
    alphabet = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    )
    assert set(b64).issubset(alphabet), f"unexpected chars in base64 output"


@pytest.mark.ipc
def test_read_tex_artifact_base64_rejects_path_outside_cache(mcp, tmp_path):
    """The command guards against arbitrary reads — any path outside
    ``~/.config/gpd/.tex-builds`` (or its XDG override) must be rejected."""
    outside = tmp_path / "outside.txt"
    outside.write_text("this file is not under the tex-builds cache")

    with pytest.raises(
        IPCError,
        match="(?i)build folder|inside its LaTeX|couldn't resolve|missing",
    ):
        invoke_via_mcp(mcp, "read_tex_artifact_base64", {"path": str(outside)})


# ---------------------------------------------------------------------------
# parse_tex_log
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_parse_tex_log_happy_path(mcp, tmp_path):
    """Feed parse_tex_log a synthesized pdflatex-style log and verify the
    structured diagnostics it returns."""
    log = tmp_path / "synthetic.log"
    log.write_text(
        "(./main.tex\n"
        "! Undefined control sequence.\n"
        "l.42 \\badmacro\n"
        "LaTeX Warning: Reference `foo' on input line 99 undefined.\n"
        "Overfull \\hbox (10pt too wide) in paragraph at lines 12--15\n"
        ")\n"
    )

    result = invoke_via_mcp(mcp, "parse_tex_log", {"logPath": str(log)})

    assert isinstance(result, dict)
    assert "errors" in result and isinstance(result["errors"], list)
    assert "warnings" in result and isinstance(result["warnings"], list)
    assert "rawLog" in result and isinstance(result["rawLog"], str)
    # At least the one error we injected.
    assert len(result["errors"]) >= 1
    assert any(
        "Undefined" in e.get("message", "") for e in result["errors"]
    ), f"expected 'Undefined' error, got {result['errors']!r}"
    # At least the LaTeX Warning + Overfull \hbox → 2 warnings.
    assert len(result["warnings"]) >= 2


@pytest.mark.ipc
def test_parse_tex_log_rejects_missing_file(mcp, tmp_path):
    """A nonexistent log path must surface an Err, not a silent empty result."""
    nowhere = tmp_path / "does-not-exist.log"

    with pytest.raises(IPCError, match="(?i)open|re-render|error log"):
        invoke_via_mcp(mcp, "parse_tex_log", {"logPath": str(nowhere)})
