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

G4.2 deepens this suite beyond shape-only assertions:
    * ``detect_tex_root`` — exercises the ``.latexmkrc`` branch and the
      sibling-``\\documentclass`` heuristic in addition to the pre-existing
      magic-comment + fallback branches.
    * ``compile_tex`` — adds a broken-LaTeX error branch in addition to the
      existing happy path and the ``no_compiler`` contract branch.
    * ``parse_tex_log`` — parametrized across warning / error-with-line /
      undefined-control-sequence / dedup / 50-cap / file-stack-attribution.
    * ``read_tex_artifact_base64`` — path-traversal (``..``), absolute system
      path (``/etc/passwd``), and symlink-escape attacks.

All tests run against the live GPD debug build through MCP (``@pytest.mark.ipc``).
We never create TeX fixtures on disk outside ``tmp_path`` (or inside the
GPD ``.tex-builds`` cache, which we clean up per test).
"""
from __future__ import annotations

import os
import shutil
import uuid
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
# strips ``% !TEX root = <path>`` from the first few lines. Escape `{stub}`
# as `{{stub}}` so `.format(root=...)` leaves the LaTeX brace intact.
TEX_WITH_MAGIC_ROOT_TEMPLATE = (
    "% !TEX root = {root}\n"
    r"\input{{stub}}"
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


def _gpd_tex_builds_root() -> Path:
    """Compute the ``.tex-builds`` cache directory the same way the Rust
    ``gpd_config_dir()`` helper does.

    The Rust side reads ``XDG_CONFIG_HOME`` when non-empty, else falls back
    to ``$HOME/.config``. We mirror that — the running GPD process inherits
    the test runner's environment, so the two computations agree.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "gpd" / ".tex-builds"


def _stage_inside_cache(filename: str, contents: bytes) -> Path:
    """Create a fresh file inside ``.tex-builds/`` and return its path.

    Caller is responsible for cleanup (remove the uniquely-named subdir).
    """
    cache_root = _gpd_tex_builds_root()
    cache_root.mkdir(parents=True, exist_ok=True)
    subdir = cache_root / f"gpd-g42-{uuid.uuid4().hex}"
    subdir.mkdir()
    p = subdir / filename
    p.write_bytes(contents)
    return p


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


# ---------------------------------------------------------------------------
# G4.2 — detect_tex_root: remaining branches
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_detect_tex_root_honors_latexmkrc(mcp, tmp_path):
    """Branch 2 of the resolver: a ``.latexmkrc`` in a parent dir with
    ``@default_files = ('foo.tex');`` redirects to that root.

    We place ``main.tex`` + ``.latexmkrc`` at the root of ``tmp_path`` and
    invoke ``detect_tex_root`` starting from a nested file with no magic
    comment and no sibling ``\\documentclass``. The resolver must walk up
    to the ``.latexmkrc`` and pick ``main.tex``.
    """
    root = tmp_path / "main.tex"
    root.write_text(TINY_TEX)
    (tmp_path / ".latexmkrc").write_text(
        "@default_files = ('main.tex');\n"
    )

    nested = tmp_path / "chapters"
    nested.mkdir()
    child = nested / "chapter1.tex"
    # No magic comment, no \documentclass — forces .latexmkrc resolution.
    child.write_text("Just some chapter prose, nothing else.\n")

    result = invoke_via_mcp(mcp, "detect_tex_root", {"startFile": str(child)})

    assert isinstance(result, str)
    assert Path(result).resolve() == root.resolve(), (
        f"expected .latexmkrc-declared root, got {result!r}"
    )


@pytest.mark.ipc
def test_detect_tex_root_honors_sibling_documentclass(mcp, tmp_path):
    """Branch 3 of the resolver: when neither the magic comment nor a
    ``.latexmkrc`` applies, scan the start file's directory for a sibling
    ``.tex`` containing ``\\documentclass``.

    We place a bare ``chapter1.tex`` (no documentclass) alongside
    ``main.tex`` (with documentclass). Invoking on the bare file must
    return the sibling that looks like a root document.
    """
    chapter = tmp_path / "chapter1.tex"
    chapter.write_text("Chapter body, no documentclass here.\n")

    sibling_root = tmp_path / "main.tex"
    sibling_root.write_text(TINY_TEX)  # contains \documentclass{article}

    result = invoke_via_mcp(
        mcp, "detect_tex_root", {"startFile": str(chapter)}
    )

    assert isinstance(result, str)
    assert Path(result).resolve() == sibling_root.resolve(), (
        f"expected sibling-with-documentclass root, got {result!r}"
    )


# ---------------------------------------------------------------------------
# G4.2 — compile_tex: additional branches
# ---------------------------------------------------------------------------


@pytest.mark.ipc
@pytest.mark.timeout(120)
def test_compile_tex_success_produces_readable_pdf(mcp, tmp_path):
    """End-to-end: compile TINY_TEX → read back the produced PDF via
    ``read_tex_artifact_base64`` and assert its header starts with ``%PDF-``.

    On hosts without a TeX compiler the contract is ``status ==
    "no_compiler"`` — a valid outcome per the task — and we short-circuit.
    """
    if not _has_tex_compiler():
        pytest.skip("no TeX compiler on host — skipping artifact chain")

    tex = tmp_path / "tiny.tex"
    tex.write_text(TINY_TEX)

    result = invoke_via_mcp(
        mcp,
        "compile_tex",
        {
            "projectId": "gpd-g42-success",
            "texFile": str(tex),
            "rootFile": None,
        },
    )

    assert isinstance(result, dict)
    status = result.get("status")
    assert status in {"success", "success_with_warnings", "no_compiler"}, (
        f"unexpected status for tiny compile: {status!r}"
    )
    if status == "no_compiler":
        pytest.skip("compiler vanished between detection and compile; skipping")

    pdf_path = result.get("pdfPath")
    assert pdf_path, f"expected pdfPath on {status}, got {result!r}"
    assert Path(pdf_path).is_file()

    # Round-trip the PDF through the base64 reader and decode to bytes.
    b64 = invoke_via_mcp(mcp, "read_tex_artifact_base64", {"path": pdf_path})
    assert isinstance(b64, str) and b64

    import base64 as _b64

    raw = _b64.b64decode(b64)
    # Every PDF starts with %PDF- per ISO 32000.
    assert raw.startswith(b"%PDF-"), (
        f"expected PDF magic header, first bytes: {raw[:8]!r}"
    )


@pytest.mark.ipc
@pytest.mark.timeout(120)
def test_compile_tex_no_compiler_or_success_contract(mcp, tmp_path):
    """Dual-mode contract: on a host lacking both ``pdflatex`` and
    ``tectonic`` the command must return ``status == "no_compiler"`` with
    ``compilerKind is None``; on a well-equipped host it must return a
    success/error status with a populated ``compilerKind``.

    This is the one test the task requires "on a host without tectonic" —
    we assert the shape that corresponds to the host we're actually on.
    """
    tex = tmp_path / "tiny.tex"
    tex.write_text(TINY_TEX)

    result = invoke_via_mcp(
        mcp,
        "compile_tex",
        {
            "projectId": "gpd-g42-nocomp",
            "texFile": str(tex),
            "rootFile": None,
        },
    )

    assert isinstance(result, dict)
    status = result.get("status")
    if not _has_tex_compiler():
        assert status == "no_compiler", (
            f"bare host must report no_compiler, got {status!r}"
        )
        assert result.get("compilerKind") in (None, "")
        assert result.get("compilerPath") in (None, "")
        assert result.get("pdfPath") in (None, "")
        assert result.get("logPath") in (None, "")
        # Diagnostics are empty for the no_compiler short-circuit.
        assert result.get("errors") == []
        assert result.get("warnings") == []
    else:
        assert status in {
            "success", "success_with_warnings", "error",
        }, f"host has a compiler but got {status!r}"
        assert isinstance(result.get("compilerKind"), str)
        assert result["compilerKind"] in {"pdflatex", "tectonic"}


@pytest.mark.ipc
@pytest.mark.timeout(120)
def test_compile_tex_broken_latex_reports_error(mcp, tmp_path):
    """Broken LaTeX — an unknown ``\\documentclass`` — must surface a
    non-success status with a populated ``logPath`` so the UI can render
    diagnostics. An unknown document class is the most portable way to
    force a no-PDF outcome across both pdflatex and tectonic.

    On bare hosts this still collapses to ``no_compiler`` (compiler
    resolution happens before the source is read).
    """
    broken = tmp_path / "broken.tex"
    # Unknown document class → catastrophic failure in either pdflatex or
    # tectonic. No .pdf is produced, the .log contains the fatal error.
    broken.write_text(
        r"\documentclass{nonexistent_class_gpd_g42_xyz}" + "\n"
        r"\begin{document}" + "\n"
        "Body." + "\n"
        r"\end{document}" + "\n"
    )

    result = invoke_via_mcp(
        mcp,
        "compile_tex",
        {
            "projectId": "gpd-g42-broken",
            "texFile": str(broken),
            "rootFile": None,
        },
    )

    assert isinstance(result, dict)
    status = result.get("status")
    if not _has_tex_compiler():
        assert status == "no_compiler"
        return

    # Primary contract: a broken compile MUST not silently report "success".
    # The status must reflect the failure, and a logPath must be present so
    # the UI can show diagnostics. Accept both "error" (no PDF) and
    # "success_with_warnings" in case a compiler still emits a partial PDF.
    assert status in {"error", "success_with_warnings"}, (
        f"broken LaTeX should not report clean success, got {status!r}"
    )
    # logPath is the load-bearing artifact for the error UI.
    assert result.get("logPath"), (
        f"expected logPath on {status}, got {result!r}"
    )
    assert Path(result["logPath"]).is_file()
    # The parse_tex_log-shaped diagnostics must include at least one error
    # or warning entry — silently returning clean diagnostics on a broken
    # source would be a regression.
    assert len(result.get("errors", []) + result.get("warnings", [])) > 0, (
        f"expected at least one diagnostic, got {result!r}"
    )


# ---------------------------------------------------------------------------
# G4.2 — parse_tex_log: parametrized log-grammar coverage
# ---------------------------------------------------------------------------


# Each case is (id, log_contents, assertion_callable). The assertion takes
# the parse result dict and raises on mismatch. We avoid lambdas with
# side-effectful asserts so pytest's diff output is useful.
def _assert_undefined_control_sequence(result: dict) -> None:
    errors = result["errors"]
    assert any("Undefined" in e.get("message", "") for e in errors), errors
    # The `l.NN` line attaches a line number to the most recent error.
    assert any(e.get("line") == 42 for e in errors), errors


def _assert_error_with_file_and_line(result: dict) -> None:
    errors = result["errors"]
    assert len(errors) >= 1, errors
    e = errors[0]
    # File-stack reconstruction attributes the error to the currently open file.
    assert e.get("file") == "./chapter1.tex", e
    assert e.get("line") == 17, e


def _assert_latex_warning(result: dict) -> None:
    warnings = result["warnings"]
    assert len(warnings) == 1, warnings
    assert "Reference" in warnings[0]["message"]
    assert warnings[0]["line"] == 99


def _assert_warning_dedup(result: dict) -> None:
    # Two identical warnings in the log collapse to a single entry.
    warnings = result["warnings"]
    assert len(warnings) == 1, (
        f"expected deduped warning (1), got {len(warnings)}: {warnings!r}"
    )


def _assert_fifty_cap(result: dict) -> None:
    # 100 `!` errors in the log → cap at 50 per the Rust `truncate(50)`.
    assert len(result["errors"]) == 50, (
        f"expected 50-cap, got {len(result['errors'])}"
    )


def _assert_file_stack_depth(result: dict) -> None:
    # Error inside the nested (./chapter1.tex ( ./nested.tex ) ) — at the
    # moment of `! Error`, nested.tex has closed so the most recent open
    # frame is chapter1.tex.
    errors = result["errors"]
    assert len(errors) >= 1, errors
    assert errors[0].get("file") == "./chapter1.tex", errors[0]


_PARSE_LOG_CASES = [
    (
        "undefined_control_sequence",
        (
            "(./main.tex\n"
            "! Undefined control sequence.\n"
            "l.42 \\badmacro\n"
            ")\n"
        ),
        _assert_undefined_control_sequence,
    ),
    (
        "error_with_file_and_line",
        (
            "(./chapter1.tex\n"
            "! Something went wrong here.\n"
            "l.17 \\oops\n"
            ")\n"
        ),
        _assert_error_with_file_and_line,
    ),
    (
        "latex_warning_line_number",
        "LaTeX Warning: Reference `foo' on input line 99 undefined.\n",
        _assert_latex_warning,
    ),
    (
        "warning_dedup",
        (
            "LaTeX Warning: Reference `foo' on input line 42 undefined.\n"
            "LaTeX Warning: Reference `foo' on input line 42 undefined.\n"
        ),
        _assert_warning_dedup,
    ),
    (
        "fifty_cap",
        "\n".join(f"! error number {i}" for i in range(100)) + "\n",
        _assert_fifty_cap,
    ),
    (
        "file_stack_reconstruction",
        # (./chapter1.tex opens on line 1 and stays open; (./sub.tex) opens
        # AND closes on line 2; the error on line 3 should attribute to
        # chapter1.tex because sub.tex popped off the stack.
        (
            "(./chapter1.tex\n"
            "(./sub.tex) some content\n"
            "! Error in outer frame.\n"
            "l.5 \\boom\n"
            ")\n"
        ),
        _assert_file_stack_depth,
    ),
]


@pytest.mark.ipc
@pytest.mark.parametrize(
    "case_id,log_contents,checker",
    _PARSE_LOG_CASES,
    ids=[c[0] for c in _PARSE_LOG_CASES],
)
def test_parse_tex_log_categories(
    mcp, tmp_path, case_id, log_contents, checker
):
    """Feed a synthesized log to ``parse_tex_log`` and assert the specific
    parser behavior the case documents.

    Cases span: undefined-control-sequence with ``l.NN`` line attribution,
    errors-with-file-attribution via the file stack, ``LaTeX Warning``
    input-line extraction, warning deduplication, the 50-cap truncation
    invariant, and file-stack-depth reconstruction across ``(…)`` nesting.
    """
    log = tmp_path / f"case_{case_id}.log"
    log.write_text(log_contents)

    result = invoke_via_mcp(mcp, "parse_tex_log", {"logPath": str(log)})

    assert isinstance(result, dict)
    assert isinstance(result.get("errors"), list)
    assert isinstance(result.get("warnings"), list)
    assert isinstance(result.get("rawLog"), str)
    # The raw log must be preserved verbatim (read_to_string round-trip).
    assert result["rawLog"] == log_contents

    checker(result)


# ---------------------------------------------------------------------------
# G4.2 — read_tex_artifact_base64: security / path-traversal tests
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_read_tex_artifact_base64_accepts_staged_cache_file(mcp):
    """Happy path: a file we stage directly under ``.tex-builds/`` must be
    readable (canonicalization keeps it inside the cache root).

    This exercises the security guard's success side without relying on a
    full compile — it pinpoints "file inside cache" as the allowed case.
    """
    staged = _stage_inside_cache("artifact.bin", b"hello from G4.2\n")
    try:
        b64 = invoke_via_mcp(
            mcp, "read_tex_artifact_base64", {"path": str(staged)}
        )
        assert isinstance(b64, str) and b64
        import base64 as _b64

        raw = _b64.b64decode(b64)
        assert raw == b"hello from G4.2\n", f"unexpected round-trip: {raw!r}"
    finally:
        # Clean up the UUID'd subdir; never touch the cache-wide root.
        try:
            staged.unlink()
        except FileNotFoundError:
            pass
        try:
            staged.parent.rmdir()
        except OSError:
            pass


@pytest.mark.ipc
def test_read_tex_artifact_base64_rejects_dotdot_traversal(mcp):
    """Path-traversal attack: a path containing ``..`` components that
    canonicalizes to a location outside ``.tex-builds`` must be refused.

    ``/tmp/../etc/passwd`` is the canonical ``..``-escape: every component
    exists (so ``canonicalize`` succeeds), the path literally contains
    ``..``, and the resolved target (`/etc/passwd`) sits well outside the
    GPD cache root.
    """
    if not Path("/etc/passwd").is_file():
        pytest.skip("/etc/passwd not present on this host (Windows?)")

    # `/tmp/..` resolves to `/`, then `etc/passwd` is appended — final
    # canonical path is `/etc/passwd`, outside the cache. The `..` is the
    # load-bearing attack component.
    traversing = "/tmp/../etc/passwd"

    with pytest.raises(
        IPCError,
        match="(?i)build folder|inside its LaTeX|couldn't resolve|missing",
    ):
        invoke_via_mcp(
            mcp, "read_tex_artifact_base64", {"path": traversing}
        )


@pytest.mark.ipc
def test_read_tex_artifact_base64_rejects_etc_passwd(mcp):
    """Security sanity: a direct absolute path to ``/etc/passwd`` must be
    refused — it exists on every Unix host and sits outside the cache.

    Together with the ``..`` case and the symlink case below, this
    triple-checks the Rust ``starts_with(cache_canon)`` guard.
    """
    # /etc/passwd always exists on macOS + Linux. On Windows this would
    # need a different target; the CI matrix for G4 is macOS+Linux.
    if not Path("/etc/passwd").is_file():
        pytest.skip("/etc/passwd not present on this host (Windows?)")

    with pytest.raises(
        IPCError,
        match="(?i)build folder|inside its LaTeX|couldn't resolve|missing",
    ):
        invoke_via_mcp(
            mcp, "read_tex_artifact_base64", {"path": "/etc/passwd"}
        )


@pytest.mark.ipc
def test_read_tex_artifact_base64_rejects_symlink_escape(mcp):
    """Symlink-escape attack: a symlink staged *inside* ``.tex-builds/``
    pointing at ``/etc/passwd`` must be refused — the Rust command
    canonicalizes the path before the containment check, so symlinks are
    resolved away.

    Without the ``canonicalize`` + ``starts_with`` guard this would have
    been a trivial sandbox escape.
    """
    if not Path("/etc/passwd").is_file():
        pytest.skip("/etc/passwd not present on this host (Windows?)")

    cache_root = _gpd_tex_builds_root()
    cache_root.mkdir(parents=True, exist_ok=True)
    subdir = cache_root / f"gpd-g42-symlink-{uuid.uuid4().hex}"
    subdir.mkdir()
    link = subdir / "link.pdf"
    try:
        os.symlink("/etc/passwd", link)
    except OSError as e:
        pytest.skip(f"cannot create symlink in .tex-builds: {e}")

    try:
        with pytest.raises(
            IPCError,
            match="(?i)build folder|inside its LaTeX|couldn't resolve|missing",
        ):
            invoke_via_mcp(
                mcp, "read_tex_artifact_base64", {"path": str(link)}
            )
    finally:
        try:
            link.unlink()
        except FileNotFoundError:
            pass
        try:
            subdir.rmdir()
        except OSError:
            pass
