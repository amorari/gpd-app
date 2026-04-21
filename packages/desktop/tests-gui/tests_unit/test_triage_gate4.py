from unittest.mock import patch, MagicMock

import pytest

from scripts.triage_gate4 import find_related_commits


@pytest.mark.unit
def test_find_related_commits_parses_git_log_output():
    mock_result = MagicMock()
    mock_result.stdout = (
        "abc123\tfix(server): foo\n"
        "def456\tfeat(ui): baz\n"
        "\n"  # empty line should be skipped
        "ghi789\ttest(ipc): bar\n"
    )
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result):
        results = find_related_commits(
            since="2026-04-19",
            paths=["packages/desktop/src-tauri/"],
        )
    assert len(results) == 3
    assert results[0] == {"sha": "abc123", "subject": "fix(server): foo"}
    assert results[1] == {"sha": "def456", "subject": "feat(ui): baz"}
    assert results[2] == {"sha": "ghi789", "subject": "test(ipc): bar"}


@pytest.mark.unit
def test_find_related_commits_empty_output():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result):
        results = find_related_commits(since="2026-04-19")
    assert results == []


@pytest.mark.unit
def test_find_related_commits_passes_paths_to_git():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as spy:
        find_related_commits(
            since="2026-04-19",
            paths=["a/b/", "c/"],
        )
    args = spy.call_args.args[0]
    assert "--" in args
    double_dash = args.index("--")
    assert args[double_dash + 1 :] == ["a/b/", "c/"]
    assert "--since=2026-04-19" in args
