import textwrap

import pytest

from scripts.flakiness.report import aggregate, to_markdown


JUNIT_PASS = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest">
        <testcase name="test_a" classname="tests.smoke.test_x"/>
        <testcase name="test_b" classname="tests.smoke.test_y"/>
      </testsuite>
    </testsuites>
    """)

JUNIT_FAIL_B = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest">
        <testcase name="test_a" classname="tests.smoke.test_x"/>
        <testcase name="test_b" classname="tests.smoke.test_y">
          <failure message="boom">tb</failure>
        </testcase>
      </testsuite>
    </testsuites>
    """)

JUNIT_ERROR_A = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest">
        <testcase name="test_a" classname="tests.smoke.test_x">
          <error message="setup failed"/>
        </testcase>
        <testcase name="test_b" classname="tests.smoke.test_y"/>
      </testsuite>
    </testsuites>
    """)


@pytest.mark.unit
def test_all_pass_reports_no_flakes(tmp_path):
    (tmp_path / "r1.xml").write_text(JUNIT_PASS)
    (tmp_path / "r2.xml").write_text(JUNIT_PASS)
    result = aggregate(tmp_path)
    assert set(result["stable"]) == {
        "tests.smoke.test_x::test_a",
        "tests.smoke.test_y::test_b",
    }
    assert result["flaky"] == []
    assert result["broken"] == []


@pytest.mark.unit
def test_mixed_pass_fail_reports_flaky(tmp_path):
    (tmp_path / "r1.xml").write_text(JUNIT_PASS)
    (tmp_path / "r2.xml").write_text(JUNIT_FAIL_B)
    (tmp_path / "r3.xml").write_text(JUNIT_PASS)
    result = aggregate(tmp_path)
    flaky_ids = [f["id"] for f in result["flaky"]]
    assert "tests.smoke.test_y::test_b" in flaky_ids
    entry = next(f for f in result["flaky"] if f["id"] == "tests.smoke.test_y::test_b")
    assert entry["pass_count"] == 2
    assert entry["fail_count"] == 1
    assert entry["total_runs"] == 3


@pytest.mark.unit
def test_error_counts_as_failure(tmp_path):
    """Setup errors bucket with test failures."""
    (tmp_path / "r1.xml").write_text(JUNIT_PASS)
    (tmp_path / "r2.xml").write_text(JUNIT_ERROR_A)
    result = aggregate(tmp_path)
    flaky_ids = [f["id"] for f in result["flaky"]]
    assert "tests.smoke.test_x::test_a" in flaky_ids


@pytest.mark.unit
def test_all_fail_is_broken_not_flaky(tmp_path):
    (tmp_path / "r1.xml").write_text(JUNIT_FAIL_B)
    (tmp_path / "r2.xml").write_text(JUNIT_FAIL_B)
    result = aggregate(tmp_path)
    assert "tests.smoke.test_y::test_b" in result["broken"]
    assert result["flaky"] == []


@pytest.mark.unit
def test_markdown_contains_counts(tmp_path):
    (tmp_path / "r1.xml").write_text(JUNIT_PASS)
    (tmp_path / "r2.xml").write_text(JUNIT_FAIL_B)
    md = to_markdown(aggregate(tmp_path))
    assert "Flakiness report" in md
    assert "2 runs" in md
    assert "test_b" in md
