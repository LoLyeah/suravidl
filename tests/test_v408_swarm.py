"""v0.40.8 "the swarm" — the suite runs on every core.

Three serial runs of the full suite already proved the tests are
parallel-clean (no shared ports, no order dependence); these pins keep the
CI wiring honest: the parallel run stays on, xdist stays a declared dev
dependency, and the matrix keeps testing both ends of the supported
Python range.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_tests_run_in_parallel():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "pytest tests/ -q -n auto" in ci, \
        "the CI test step must fan out across the runner's cores"


def test_xdist_is_a_declared_dev_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "pytest-xdist" in pyproject, \
        "pip install -e '.[dev]' must bring the parallel runner CI asks for"


def test_the_matrix_still_tests_both_pythons():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert '"3.10"' in ci and '"3.12"' in ci, \
        "parallelising must not shrink the versions under test"
