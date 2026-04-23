# mutmut configuration. Runs against a single module at a time; CI job
# selects via `mutmut run --paths-to-mutate gpd_tests/helpers/ipc.py`.
#
# Targeted mutation runs only — full-suite mutation is out of scope.
# See scripts/run_mutation_test.sh for the CI-facing wrapper.

runner = "uv run pytest tests_unit -m unit -q -x"
tests_dir = "tests_unit/"


def pre_mutation(context):
    """Skip mutating lines tagged with `# pragma: no mutate`."""
    line = context.current_source_line.strip() if context.current_source_line else ""
    if "# pragma: no mutate" in line:
        context.skip = True
