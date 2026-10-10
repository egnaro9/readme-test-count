"""The CLI, and the coupling that extraction removed.

The pre-extraction script ended in

    check(pathlib.Path(__file__).resolve().parent.parent)

which is correct only while the file sits in `<root>/scripts/`. That line is the single reason
the tool could not be installed, so these tests pin the replacement: a root argument that
defaults to the working directory and resolves relative paths.
"""
from __future__ import annotations

import pathlib

import pytest

from readme_test_count.cli import main


@pytest.fixture
def project(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_a(): pass\ndef test_b(): pass\n")
    (tmp_path / "README.md").write_text("2 tests")
    return tmp_path


def test_an_explicit_root_is_checked(project: pathlib.Path, capsys) -> None:
    assert main([str(project)]) == 0
    assert "agree on 2 tests" in capsys.readouterr().out


def test_the_root_defaults_to_the_working_directory(
    project: pathlib.Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(project)
    assert main([]) == 0
    assert "agree on 2 tests" in capsys.readouterr().out


def test_a_wrong_count_exits_nonzero_and_writes_to_stderr(
    project: pathlib.Path, capsys
) -> None:
    (project / "README.md").write_text("9 tests")
    assert main([str(project)]) == 1
    captured = capsys.readouterr()
    assert "says [9] tests" in captured.err
    assert captured.out == "", "a failure must not be reported on stdout"


def test_a_root_that_is_not_a_directory_fails(tmp_path: pathlib.Path, capsys) -> None:
    assert main([str(tmp_path / "nope")]) == 1
    assert "is not a directory" in capsys.readouterr().err


def test_a_file_passed_as_the_root_fails_rather_than_being_read(
    project: pathlib.Path, capsys
) -> None:
    assert main([str(project / "README.md")]) == 1
    assert "is not a directory" in capsys.readouterr().err


def test_the_exemption_note_is_printed_on_success(project: pathlib.Path, capsys) -> None:
    """A passing run must still say what it declined to count."""
    (project / "tests" / "test_db.py").write_text(
        '# readme-test-count: exempt\n'
        'import pytest\npytest.importorskip("absent_module")\ndef test_z(): pass\n'
    )
    assert main([str(project)]) == 0
    out = capsys.readouterr().out
    assert "1 test file(s) exempt by declaration and NOT counted" in out
    assert "tests/test_db.py" in out


def test_the_tests_dir_option_reaches_the_check(tmp_path: pathlib.Path, capsys) -> None:
    (tmp_path / "README.md").write_text("1 tests")
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec" / "test_a.py").write_text("def test_a(): pass\n")
    (tmp_path / "spec" / "test_gone.py").write_text(
        'import pytest\npytest.importorskip("absent_module")\ndef test_z(): pass\n'
    )
    assert main([str(tmp_path), "--tests-dir", "spec"]) == 1
    assert "spec/test_gone.py" in capsys.readouterr().err
