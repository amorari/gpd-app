"""Security-focused IPC boundary tests (G7.4).

Consolidates vectors that probe the trust boundary between the webview and
the Tauri main process. Complements the per-command contract suites in
``tests/ipc/`` by explicitly targeting:

    * filesystem containment (path traversal, absolute-path escape)
    * shell/command-injection attempts in TeX sources
    * DOM-level XSS vectors in the markdown renderer (iframes, onerror
      handlers, ``javascript:`` URLs)
    * clean-error contracts when path-style commands are called with
      invalid / missing arguments (must surface ``IPCError``, never panic)

All tests are dual-marked ``@pytest.mark.security + @pytest.mark.ipc``.

Related work:
    * G4.2 (``tests/ipc/test_tex_compiler.py``) covers the ``read_tex_artifact_base64``
      path-traversal + symlink-escape cases — not duplicated here.
    * G4.3 (``tests/ipc/test_tectonic_markdown_cli.py``) covers the ``<script>``
      XSS vector — extended here with iframe / onerror / javascript-URL vectors.

Findings (as of 2026-04-20):
    * The markdown renderer runs comrak with ``render.r#unsafe = true``
      (``packages/desktop/src-tauri/src/markdown.rs:50``). That flag lets raw
      ``<iframe>``, ``<img onerror=...>`` and ``javascript:`` URLs pass
      through unchanged. Tests below assert sanitization; if they fail, that
      IS the bug, and the fix direction is staged in
      ``docs/gpd-app-patches/SECURITY-markdown-unsafe-html.patch``.

Destructive commands are NEVER actually executed — we construct payloads
that WOULD delete / leak data if the product were vulnerable, and assert
that the sentinel state survives untouched.
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


# ---------------------------------------------------------------------------
# project_fs: absolute paths outside $HOME
# ---------------------------------------------------------------------------


@pytest.mark.security
@pytest.mark.ipc
def test_project_fs_rejects_absolute_paths_outside_home(mcp):
    """Create a project directly under ``/etc``.

    ``/etc`` exists and is a directory, so the ``is_dir()`` guard in
    ``create_project_directory`` lets us through — but ``create_dir`` then
    fails with ``EACCES`` on every non-root POSIX host. The Rust wrapper
    surfaces that as an ``IPCError`` whose message starts with
    ``"Couldn't create the folder"``.

    The security property we assert: the command does NOT silently succeed
    and does NOT panic. Either a hard rejection (any branch of the Err
    ladder) or a permission-denied wrap is acceptable — we just guarantee
    it doesn't write into ``/etc``.

    Skipped as root: root CAN write to ``/etc``, and creating a real
    directory there would leak test state outside the sandbox.
    """
    if os.name == "posix" and os.geteuid() == 0:
        pytest.skip("running as root — can actually write to /etc; skipping")

    name = f"gpd-g74-outside-home-{uuid.uuid4().hex}"
    with pytest.raises(IPCError) as exc:
        invoke_via_mcp(
            mcp,
            "create_project_directory",
            {"parent": "/etc", "name": name},
        )

    msg = str(exc.value).lower()
    # The Rust side either wraps the OS error as "Couldn't create the
    # folder..." (Err branch 6) or bubbles a lower-level "permission
    # denied". Accept either — the point is the command refused.
    assert any(
        hint in msg
        for hint in ("couldn't create", "permission", "denied", "doesn't exist")
    ), f"expected permission-denied rejection, got: {msg!r}"

    # Belt-and-braces: the directory MUST NOT exist even if the error
    # somehow fires after the write succeeds on an exotic platform.
    assert not (Path("/etc") / name).exists(), (
        f"security: /etc/{name} was created despite the error — check "
        f"create_project_directory write ordering"
    )


# ---------------------------------------------------------------------------
# tex_compiler: shell-injection via \input{|...} (pipe) command
# ---------------------------------------------------------------------------


def _has_tex_compiler() -> bool:
    return (
        shutil.which("pdflatex") is not None
        or shutil.which("tectonic") is not None
    )


@pytest.mark.security
@pytest.mark.ipc
@pytest.mark.timeout(120)
def test_tex_command_injection_via_input_brace(mcp, tmp_path):
    """TeX historically allows ``\\input{|command}`` to execute a shell
    command on some engines (``pdflatex --shell-escape``). Modern engines
    default to ``--no-shell-escape`` and ``openin_any = p`` / ``openout_any
    = p``, which forbid piped reads/writes.

    Sentinel-based assertion: we create a real marker file in ``tmp_path``,
    then feed compile_tex a document whose ``\\input{|rm -rf <marker>}``
    command WOULD delete that marker if the engine honored the pipe. After
    compile returns, the marker file must still be on disk. If it isn't,
    the product is mis-configuring the compiler invocation — that is a
    real security finding worth a patch.

    We NEVER execute the destructive command ourselves; we only let the
    compiler see the payload and trust its built-in lockdown.
    """
    if not _has_tex_compiler():
        pytest.skip("no TeX compiler on host — payload can't be exercised")

    marker = tmp_path / f"sentinel-{uuid.uuid4().hex}.txt"
    marker.write_text("SURVIVE\n")
    assert marker.is_file()

    # The payload: an \input whose argument is a pipe to `rm -rf <marker>`.
    # Bracketed exactly as the (in)famous TeX command-injection pattern.
    malicious_path = str(marker).replace("\\", "\\\\")
    tex_source = (
        r"\documentclass{article}" + "\n"
        r"\begin{document}" + "\n"
        r"Normal text." + "\n"
        # The brace-delimited `|cmd` form. If the engine accepts pipes we
        # want it to SEE the payload; it should reject the pipe and either
        # error out or just fail to read the file. Either way, the marker
        # survives.
        + "\\input{|rm -rf " + malicious_path + "}\n"
        + r"\end{document}" + "\n"
    )

    broken = tmp_path / "injection.tex"
    broken.write_text(tex_source)

    # Run compile; we don't care whether it succeeds or errors — only that
    # the destructive shell never fires.
    try:
        result = invoke_via_mcp(
            mcp,
            "compile_tex",
            {
                "projectId": "gpd-g74-inject",
                "texFile": str(broken),
                "rootFile": None,
            },
        )
    except IPCError:
        # Even a hard compile error is fine — the injection must not run.
        result = None

    # Primary security assertion: the sentinel must still exist.
    assert marker.is_file(), (
        f"SECURITY FINDING: marker file {marker} was deleted — the TeX "
        f"compiler executed the \\input{{|rm -rf ...}} payload. The "
        f"compiler is running with shell-escape enabled or with "
        f"openin_any != p. See docs/gpd-app-patches/"
        f"SECURITY-tex-shell-escape.patch for the fix direction."
    )
    # Sanity: its contents are intact.
    assert marker.read_text() == "SURVIVE\n", (
        "SECURITY FINDING: marker file was truncated/overwritten by the "
        "injected TeX command — partial injection succeeded."
    )

    # If we got a result, it must be a well-formed dict (not a panic).
    if result is not None:
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# markdown: iframe + img onerror XSS vectors
# ---------------------------------------------------------------------------


@pytest.mark.security
@pytest.mark.ipc
def test_markdown_iframe_is_escaped(mcp):
    """Extension of G4.3's ``<script>`` test: raw ``<iframe src=javascript:>``
    and ``<img src=x onerror=alert(1)>`` tags in markdown source must NOT
    survive into the rendered HTML as executable elements.

    Currently ``markdown.rs::parse_markdown`` sets ``render.r#unsafe =
    true``, which means raw HTML passes through. If this test fails, that
    IS a real XSS sink: any caller that renders parse_markdown_command
    output with ``innerHTML`` (which the product does — the markdown panel
    streams HTML into the DOM) will execute attacker-supplied script.

    Fix direction staged at
    ``docs/gpd-app-patches/SECURITY-markdown-unsafe-html.patch``.
    """
    fixture = (
        "# Heading\n\n"
        '<iframe src="javascript:alert(1)"></iframe>\n\n'
        '<img src=x onerror="alert(1)">\n\n'
        "Trailing paragraph.\n"
    )
    html = invoke_via_mcp(mcp, "parse_markdown_command", {"markdown": fixture})
    assert isinstance(html, str)
    lowered = html.lower()

    # Security finding — currently expected to FAIL because markdown.rs
    # has `render.r#unsafe = true`. When it fails, the failure is the
    # real security regression, not a test bug.
    assert "<iframe" not in lowered, (
        "SECURITY FINDING: raw <iframe> tag survived markdown rendering — "
        "this is a DOM XSS sink (javascript: URL inside iframe executes "
        "in the webview). See docs/gpd-app-patches/"
        "SECURITY-markdown-unsafe-html.patch for the fix direction."
    )
    assert "onerror" not in lowered, (
        "SECURITY FINDING: raw onerror handler survived markdown rendering — "
        "this is a DOM XSS sink. <img src=x onerror=alert(1)> triggers on "
        "every render. See docs/gpd-app-patches/"
        "SECURITY-markdown-unsafe-html.patch for the fix direction."
    )
    # The raw ``javascript:`` literal must not appear as an attribute value
    # (it's fine inside escaped text where ``:`` is benign).
    assert 'src="javascript:' not in lowered and "src='javascript:" not in lowered, (
        "SECURITY FINDING: raw javascript: URL survived in src attribute"
    )


@pytest.mark.security
@pytest.mark.ipc
def test_markdown_javascript_url_in_link_is_sanitized(mcp):
    """Markdown link with a ``javascript:`` URL target.

    comrak's built-in ``dangerous_url`` check would normally strip
    ``javascript:`` hrefs — BUT the ``ExternalLinkFormatter`` in
    ``markdown.rs`` short-circuits that check with
    ``context.options.render.r#unsafe || !dangerous_url(url)``. Because
    ``render.r#unsafe = true``, the guard is bypassed and the javascript:
    URL ends up in the rendered href.

    We assert the rendered HTML does NOT have ``href="javascript:...``. If
    it does, clicking the rendered link in the webview executes attacker
    JS. Fix direction: either set ``r#unsafe = false`` (the nuclear
    option) or remove the ``r#unsafe ||`` short-circuit in the
    ExternalLinkFormatter so dangerous_url is always honored.
    """
    fixture = "[click me](javascript:alert(1))\n"
    html = invoke_via_mcp(mcp, "parse_markdown_command", {"markdown": fixture})
    assert isinstance(html, str)
    lowered = html.lower()

    # The core assertion: no javascript: URL in any href.
    assert 'href="javascript:' not in lowered, (
        "SECURITY FINDING: javascript: URL survived markdown link "
        "rendering — clicking the link executes attacker JS in the "
        "webview. See docs/gpd-app-patches/"
        "SECURITY-markdown-unsafe-html.patch for the fix direction."
    )
    assert "href='javascript:" not in lowered, (
        "SECURITY FINDING: javascript: URL survived (single-quoted href)"
    )
    # Belt-and-braces: the literal `javascript:` string must not appear
    # inside *any* attribute value. It can still appear as visible text
    # inside the rendered anchor (that's just prose) — so we only ban
    # the specific attribute-value form tested above. No extra assertion
    # needed here beyond those two.


# ---------------------------------------------------------------------------
# path-style command: clean error on missing / invalid arg (no panic)
# ---------------------------------------------------------------------------


@pytest.mark.security
@pytest.mark.ipc
def test_path_info_requires_directory_or_errors_cleanly(mcp):
    """A path-style IPC command called without a proper value must raise a
    clean ``IPCError`` — never a Rust panic that would take down the main
    process.

    We exercise ``check_project_accessible``, which is the canonical
    path-info command (returns ``"ok" | "missing" | "locked"``):

      * no arg at all → Tauri deserialization error, IPCError.
      * arg present but empty string → Rust treats "" as "current dir" in
        some branches; we require the command to either return a sentinel
        or raise — but never produce an uncaught panic.
      * arg of the wrong type (list) → deserialization error, IPCError.

    In every case we assert ``IPCError`` is raised and the message is
    non-empty and does not contain "panic" / "thread 'main' panicked".
    """

    def _assert_clean_error(exc: IPCError) -> None:
        msg = str(exc)
        assert msg, "IPCError must carry a message"
        lowered = msg.lower()
        assert "panic" not in lowered, (
            f"SECURITY FINDING: IPC call panicked instead of returning an "
            f"Err — message: {msg!r}"
        )
        assert "thread 'main' panicked" not in lowered, (
            f"SECURITY FINDING: main-process panic leaked through IPC: {msg!r}"
        )

    # Case 1: missing arg entirely. Tauri's deserializer rejects this.
    with pytest.raises(IPCError) as exc1:
        invoke_via_mcp(mcp, "check_project_accessible", {})
    _assert_clean_error(exc1.value)

    # Case 2: arg of the wrong type (list instead of string). Must raise a
    # clean deserialization error, not panic.
    with pytest.raises(IPCError) as exc2:
        invoke_via_mcp(
            mcp, "check_project_accessible", {"path": ["not", "a", "string"]}
        )
    _assert_clean_error(exc2.value)

    # Case 3: arg present but empty string. The Rust command will call
    # ``std::fs::read_dir("")`` which returns ``ErrorKind::NotFound`` on
    # most platforms → mapped to ``Ok("missing")``. We accept either that
    # mapping OR an IPCError — both are clean outcomes. The assertion is
    # "no panic".
    try:
        result = invoke_via_mcp(
            mcp, "check_project_accessible", {"path": ""}
        )
    except IPCError as e:
        _assert_clean_error(e)
    else:
        # If it returned Ok, it must be one of the documented sentinels.
        assert result in {"ok", "missing", "locked"}, (
            f"empty path returned unexpected value {result!r}; expected "
            f"a sentinel or IPCError"
        )
