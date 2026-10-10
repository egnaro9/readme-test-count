"""Every documented failure mode, pinned.

The pre-extraction version carried a `--selftest` that wrote a README and checked six exit
codes. These are those six cases plus the ones the selftest could not reach, and they assert
the collected COUNT as well as the verdict. A test that only asserts exit 1 passes for any
reason the tool happens to fail, including a crash, so each case here names the number that
had to travel from the fixture through pytest and back.
"""
from __future__ import annotations

import pathlib

import pytest

from readme_test_count import CollectionError, collect, evaluate, silent_empty_test_files

THREE_TESTS = "def test_a(): pass\ndef test_b(): pass\ndef test_c(): pass\n"


@pytest.fixture
def project(tmp_path: pathlib.Path) -> pathlib.Path:
    """A minimal project with exactly three collectable tests and no README yet."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(THREE_TESTS)
    return tmp_path


def readme(root: pathlib.Path, text: str) -> pathlib.Path:
    p = root / "README.md"
    p.write_text(text)
    return p


# ---- the six cases the original selftest covered ----


def test_a_correct_count_passes(project: pathlib.Path) -> None:
    readme(project, "3 tests, all green")
    r = evaluate(project)
    assert r.ok
    assert r.exit_code == 0
    assert r.collected == 3
    assert r.declared == [3]


def test_a_wrong_count_fails(project: pathlib.Path) -> None:
    readme(project, "4 tests, all green")
    r = evaluate(project)
    assert not r.ok
    assert r.collected == 3
    assert r.declared == [4]
    assert "says [4] tests" in "\n".join(r.lines)


def test_every_occurrence_must_match_not_just_the_first(project: pathlib.Path) -> None:
    """Two of the five audited repositories stated the count twice, one with both stale."""
    readme(project, "3 tests here and 4 tests there")
    r = evaluate(project)
    assert not r.ok
    assert r.declared == [3, 4]
    assert "2 count(s) found, 1 wrong" in "\n".join(r.lines)


def test_a_missing_count_fails_rather_than_passing_vacuously(project: pathlib.Path) -> None:
    """"Nothing to check" is the most common way a check stops checking."""
    readme(project, "no number at all")
    r = evaluate(project)
    assert not r.ok
    assert r.collected == 3
    assert r.declared == []
    assert "advertises no test count" in "\n".join(r.lines)
    # and it must say what to write, or the failure is a dead end
    assert "'3 tests'" in "\n".join(r.lines)


def test_singular_prose_is_not_a_declaration(project: pathlib.Path) -> None:
    """A dataset described as "300 test claims" is not a claim about this suite."""
    readme(project, "300 test claims from SciFact")
    r = evaluate(project)
    assert not r.ok, "singular prose must not be read as a declaration"
    assert r.declared == [], "300 was captured as a declared count"


def test_a_silently_skipped_test_file_fails(project: pathlib.Path) -> None:
    """pytest reports no error and no mention, so the count looks healthy and is wrong."""
    readme(project, "3 tests, all green")
    (project / "tests" / "test_optional.py").write_text(
        'import pytest\n'
        'pytest.importorskip("a_module_that_is_not_installed")\n'
        'def test_z(): pass\n'
    )
    r = evaluate(project)
    assert not r.ok, "an importorskip-skipped module left the count agreeing with a stale README"
    assert r.collected == 3, "pytest really did report 3, which is the whole problem"
    assert "contributed no collected test" in "\n".join(r.lines)
    assert "tests/test_optional.py" in "\n".join(r.lines)


# ---- the cases the selftest could not reach ----


def test_an_exempt_file_is_allowed_and_reported(project: pathlib.Path) -> None:
    """An exemption nobody can see is how a check stops checking, so it is printed."""
    readme(project, "3 tests, all green")
    (project / "tests" / "test_needs_a_database.py").write_text(
        '# readme-test-count: exempt, this needs the postgres service from the other CI job\n'
        'import pytest\n'
        'pytest.importorskip("psycopg_that_is_not_installed")\n'
        'def test_z(): pass\n'
    )
    r = evaluate(project)
    assert r.ok
    assert r.exempt == ["tests/test_needs_a_database.py"]


def test_the_pre_extraction_exempt_marker_is_still_honoured(project: pathlib.Path) -> None:
    """The five repositories this came from have the old marker in their test files."""
    readme(project, "3 tests, all green")
    (project / "tests" / "test_legacy.py").write_text(
        '# check-readme-test-count: exempt\n'
        'import pytest\n'
        'pytest.importorskip("not_installed_either")\n'
        'def test_z(): pass\n'
    )
    r = evaluate(project)
    assert r.ok, "migrating repos would start failing on an exemption they already declared"
    assert r.exempt == ["tests/test_legacy.py"]


def test_no_readme_fails(tmp_path: pathlib.Path) -> None:
    r = evaluate(tmp_path)
    assert not r.ok
    assert "no README.md" in "\n".join(r.lines)


def test_a_collection_that_errors_is_not_read_as_zero_tests(tmp_path: pathlib.Path) -> None:
    """The failure mode that makes the whole check pointless: 0 == 0 agrees with nothing."""
    readme(tmp_path, "0 tests")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_broken.py").write_text("this is not python at all (((\n")
    r = evaluate(tmp_path)
    assert not r.ok, "a broken collection agreed with a README advertising zero tests"
    assert r.collected is None


def test_collect_raises_rather_than_returning_zero(tmp_path: pathlib.Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_broken.py").write_text("def (((\n")
    with pytest.raises(CollectionError):
        collect(tmp_path)


def test_several_mentions_all_correct_pass(project: pathlib.Path) -> None:
    readme(project, "3 tests at the top.\n\nStill 3 tests down here.\n")
    r = evaluate(project)
    assert r.ok
    assert r.declared == [3, 3]
    assert "2 mentions" in "\n".join(r.lines)


def test_one_mention_is_reported_in_the_singular(project: pathlib.Path) -> None:
    readme(project, "3 tests")
    assert "1 mention)" in "\n".join(evaluate(project).lines)


def test_a_project_with_no_tests_dir_skips_the_empty_file_rule(tmp_path: pathlib.Path) -> None:
    """Collection still happened, so there is nothing to cross-check against the filesystem."""
    readme(tmp_path, "1 tests")
    (tmp_path / "test_flat.py").write_text("def test_a(): pass\n")
    r = evaluate(tmp_path)
    assert r.ok
    assert r.collected == 1


def test_a_custom_tests_dir_is_honoured(tmp_path: pathlib.Path) -> None:
    """The reason extraction needed an option at all: strangers do not all use tests/."""
    readme(tmp_path, "1 tests")
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec" / "test_a.py").write_text("def test_a(): pass\n")
    (tmp_path / "spec" / "test_skipped.py").write_text(
        'import pytest\npytest.importorskip("nope_not_here")\ndef test_z(): pass\n'
    )
    assert evaluate(tmp_path, tests_dir="spec").ok is False, "the skipped file was not noticed"
    # and the same tree passes when the rule is pointed somewhere empty, which is why the
    # default matters more than the option
    assert evaluate(tmp_path, tests_dir="no_such_dir").ok is True


def test_silent_empty_test_files_reads_the_filesystem_not_the_count(
    project: pathlib.Path,
) -> None:
    """Direct unit on the cross-check, so a refactor of evaluate() cannot hide it."""
    (project / "tests" / "test_never_collected.py").write_text("def test_q(): pass\n")
    stdout = "tests/test_x.py::test_a\ntests/test_x.py::test_b\n3 tests collected\n"
    missing, exempt = silent_empty_test_files(project, stdout)
    assert missing == ["tests/test_never_collected.py"]
    assert exempt == []


# ---- the hole the first consumer found (2026-10-10) ----
#
# pytest prints a count even when modules failed to import: "117 tests collected, 6 errors",
# exit 2. The original read that number. It was caught while migrating deadgate, whose suite
# collected 117 of its 223 tests because the package under test was not installed in the
# environment doing the check. A partial count is not a smaller truth, it is a different
# number, and it would have agreed with a README stating 117.


def test_a_partial_collection_with_import_errors_is_not_a_count(tmp_path: pathlib.Path) -> None:
    readme(tmp_path, "2 tests")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_fine.py").write_text(THREE_TESTS[: THREE_TESTS.index("def test_c")])
    (tmp_path / "tests" / "test_broken_import.py").write_text(
        "import a_module_that_does_not_exist\ndef test_q(): pass\n"
    )
    r = evaluate(tmp_path)
    assert not r.ok, "a collection with import errors was accepted as the project's count"
    assert r.collected is None, "the partial count leaked through as if it were real"
    joined = "\n".join(r.lines)
    assert "exited 2" in joined
    assert "partial or interrupted collection is not a test count" in joined
    # and it must NOT blame importorskip, which is a different diagnosis entirely
    assert "importorskip" not in joined


def test_collect_raises_on_a_partial_collection(tmp_path: pathlib.Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_a(): pass\n")
    (tmp_path / "tests" / "test_bad.py").write_text("import nope_not_a_module\n")
    with pytest.raises(CollectionError, match="exited 2"):
        collect(tmp_path)


def test_a_project_with_no_tests_at_all_fails(tmp_path: pathlib.Path) -> None:
    """pytest exits 5 for zero collected. Zero is a number, and it is not a suite."""
    readme(tmp_path, "0 tests")
    r = evaluate(tmp_path)
    assert not r.ok, "an empty project agreed with a README advertising zero tests"
    assert "exited 5" in "\n".join(r.lines)
