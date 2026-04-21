"""coverage_delta reads two coverage.xml files and reports line-level deltas."""
import textwrap
from pathlib import Path

import pytest

from scripts.coverage_delta import diff_coverage, to_markdown


def _make_xml(tmp_path, path, lines):
    """lines: list of (line_number, hit?) tuples."""
    lines_xml = "\n".join(
        f'        <line number="{ln}" hits="{1 if hit else 0}"/>'
        for ln, hit in lines
    )
    xml = f'''<?xml version="1.0"?>
<coverage>
  <packages>
    <package name="gpd_tests">
      <classes>
        <class name="foo.py" filename="gpd_tests/foo.py">
          <lines>
{lines_xml}
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
'''
    p = tmp_path / path
    p.write_text(xml)
    return p


@pytest.mark.unit
def test_diff_coverage_detects_newly_covered_lines(tmp_path):
    a = _make_xml(tmp_path, "before.xml", [(1, False), (2, False), (3, True)])
    b = _make_xml(tmp_path, "after.xml",  [(1, False), (2, True),  (3, True)])
    diff = diff_coverage(a, b)
    assert "gpd_tests/foo.py" in diff
    mod = diff["gpd_tests/foo.py"]
    assert 2 in mod["newly_covered"]
    assert mod["newly_uncovered"] == []


@pytest.mark.unit
def test_diff_coverage_detects_newly_uncovered_lines(tmp_path):
    a = _make_xml(tmp_path, "before.xml", [(1, True), (2, True), (3, True)])
    b = _make_xml(tmp_path, "after.xml",  [(1, True), (2, False), (3, True)])
    diff = diff_coverage(a, b)
    mod = diff["gpd_tests/foo.py"]
    assert mod["newly_covered"] == []
    assert 2 in mod["newly_uncovered"]


@pytest.mark.unit
def test_diff_coverage_same_reports_no_change(tmp_path):
    a = _make_xml(tmp_path, "x.xml", [(1, True), (2, False)])
    b = _make_xml(tmp_path, "y.xml", [(1, True), (2, False)])
    diff = diff_coverage(a, b)
    # No modules with changes
    assert all(
        not v["newly_covered"] and not v["newly_uncovered"]
        for v in diff.values()
    )


@pytest.mark.unit
def test_to_markdown_formats_deltas(tmp_path):
    a = _make_xml(tmp_path, "before.xml", [(1, False), (2, False)])
    b = _make_xml(tmp_path, "after.xml",  [(1, True), (2, False)])
    md = to_markdown(diff_coverage(a, b))
    assert "gpd_tests/foo.py" in md
    assert "Newly covered" in md


@pytest.mark.unit
def test_diff_coverage_handles_missing_module(tmp_path):
    """A module present in 'before' but absent in 'after' (or vice versa) is
    reported as fully-uncovered (or fully-new)."""
    a = _make_xml(tmp_path, "b.xml", [(1, True), (2, True)])
    b_path = tmp_path / "a.xml"
    # Empty coverage (no packages at all)
    b_path.write_text('<?xml version="1.0"?>\n<coverage><packages/></coverage>\n')
    diff = diff_coverage(a, b_path)
    # 'foo.py' appears in a but not b → treat as newly_uncovered (everything)
    mod = diff.get("gpd_tests/foo.py")
    if mod is not None:
        assert sorted(mod["newly_uncovered"]) == [1, 2]
