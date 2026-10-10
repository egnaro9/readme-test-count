"""Fail if README.md's advertised test count disagrees with the suite.

Why this exists. On 2026-10-07 five repositories were audited and ALL FIVE advertised a stale
test count: 42 where there were 58, 45 where there were 60, 97 where there were 150. Every
number had been true when it was written and nothing re-checked it, which is the same defect
those repositories had just been audited for: a claim with no check behind it.

It FAILS CLOSED, deliberately, in four ways a looser version would let pass:

  - a README with NO advertised count fails, rather than passing because there was nothing to
    compare. "Nothing to check" is the most common way a check stops checking.
  - a collection that errors fails. Both ways: one that prints no number at all, and one
    that prints a number ALONGSIDE import errors. pytest says "117 tests collected, 6 errors"
    and exits 2, and reading that 117 is how this tool briefly had the defect it exists to
    catch. Found by migrating its first consumer.
  - EVERY occurrence must match, not the first. Two of the five repositories stated the count
    twice, and one of them had both stale.
  - a test FILE that contributes no collected test fails. This one was learned hours after the
    rest shipped: a module opening with `pytest.importorskip("optional_dep")` vanishes at
    collection with NO error and no mention, so pytest says "58 tests collected" and means it.
    An earlier version read that 58, agreed with a README freshly edited to match, and would
    have frozen the wrong number in place; CI, which installed the optional extra, collected
    67. A count is only meaningful if the environment is complete, and the only evidence of
    incompleteness is a file on disk that produced nothing.

The declaration pattern is `\\b(\\d+) tests\\b`: plural and word-bounded, so prose like
"300 test claims" is not mistaken for a declaration. Write a historical count without the
word, or this will rightly object to it.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field

DECLARED = re.compile(r"\b(\d+) tests\b")
COLLECTED = re.compile(r"^(\d+) tests? collected", re.M)

# A test file may opt out of the empty-file rule by saying so in its own text. An exemption
# nobody can see is how a check stops checking, so it lives in the file and gets printed.
EXEMPT = "readme-test-count: exempt"

# The marker the tool was called before extraction, still honoured so the five repositories it
# came from can migrate without editing their test files.
LEGACY_EXEMPT = "check-readme-test-count: exempt"

DEFAULT_TESTS_DIR = "tests"


@dataclass
class Result:
    """The verdict, separated from printing it, so tests can assert on the decision."""

    ok: bool
    lines: list[str] = field(default_factory=list)
    collected: int | None = None
    declared: list[int] = field(default_factory=list)
    exempt: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1


# pytest's own exit codes, which are a stronger signal than its summary text.
EXIT_MEANING = {
    2: "pytest was interrupted, which for --collect-only means at least one module failed to "
       "import. The count it printed covers only the modules that did load.",
    3: "an internal pytest error.",
    4: "pytest usage error.",
    5: "no tests were collected at all.",
}


def collect(root: pathlib.Path) -> tuple[int, str]:
    """Return (collected count, pytest's stdout). Raises CollectionError if unusable.

    The exit code is checked BEFORE the count, and that ordering is the whole point. A
    collection with import errors still prints a number: pytest reports
    "117 tests collected, 6 errors" and exits 2. An earlier version of this read the 117 and
    treated it as the project's count, which was found by migrating the first consumer, whose
    suite collected 117 of its 223 tests in an incomplete environment. A partial count is not
    a smaller truth, it is a different number.
    """
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        why = EXIT_MEANING.get(p.returncode, "pytest exited nonzero.")
        raise CollectionError(
            f"pytest --collect-only exited {p.returncode}: {why}\n"
            "A partial or interrupted collection is not a test count.\n"
            + (p.stdout or p.stderr)[-1500:]
        )
    m = COLLECTED.search(p.stdout)
    if not m:
        raise CollectionError(
            "could not read a test count from pytest --collect-only.\n"
            "A collection that does not report a number is not zero tests, it is an error.\n"
            + (p.stdout or p.stderr)[-1500:]
        )
    return int(m.group(1)), p.stdout


class CollectionError(RuntimeError):
    """pytest did not report a count. Never treated as zero tests."""


def silent_empty_test_files(
    root: pathlib.Path, stdout: str, tests_dir: str = DEFAULT_TESTS_DIR
) -> tuple[list[str], list[str]]:
    """Test files on disk that contributed no collected test, and the declared exemptions.

    A module skipped by `pytest.importorskip` leaves no error and no line of output, so the
    only way to notice is to compare the collection against the filesystem.
    """
    d = root / tests_dir
    if not d.is_dir():
        return [], []
    seen = {line.split("::", 1)[0].strip() for line in stdout.splitlines() if "::" in line}
    missing: list[str] = []
    exempt: list[str] = []
    for f in sorted(d.rglob("test_*.py")):
        rel = f.relative_to(root).as_posix()
        if any(s == rel or s.endswith("/" + rel) or s.endswith(rel) for s in seen):
            continue
        # A module can be legitimately gated on something CI provides in a SEPARATE job, such
        # as a database service. That is a human decision, so it is declared in the file.
        text = f.read_text(encoding="utf-8", errors="replace")
        (exempt if (EXEMPT in text or LEGACY_EXEMPT in text) else missing).append(rel)
    return missing, exempt


def evaluate(root: pathlib.Path, tests_dir: str = DEFAULT_TESTS_DIR) -> Result:
    """Decide, without printing. The CLI prints; the tests assert on this."""
    readme = root / "README.md"
    if not readme.is_file():
        return Result(ok=False, lines=["FAIL: no README.md to check"])

    try:
        actual, stdout = collect(root)
    except CollectionError as exc:
        return Result(ok=False, lines=[f"FAIL: {exc}"])

    empty, exempt = silent_empty_test_files(root, stdout, tests_dir)
    if empty:
        return Result(
            ok=False,
            collected=actual,
            exempt=exempt,
            lines=[
                f"FAIL: {len(empty)} test file(s) contributed no collected test: "
                + ", ".join(empty),
                "       Usually an optional extra is missing, so a module guarded by",
                "       pytest.importorskip vanished without an error. The count from this",
                "       environment is NOT the project's count. Install every extra CI",
                "       installs and re-run.",
            ],
        )

    declared = [int(n) for n in DECLARED.findall(readme.read_text(encoding="utf-8"))]
    if not declared:
        return Result(
            ok=False,
            collected=actual,
            exempt=exempt,
            lines=[
                "FAIL: README.md advertises no test count, so nothing was checked.",
                f"       The suite collects {actual}. State it as '{actual} tests', or this",
                "       check is decorative.",
            ],
        )

    wrong = [n for n in declared if n != actual]
    if wrong:
        return Result(
            ok=False,
            collected=actual,
            declared=declared,
            exempt=exempt,
            lines=[
                f"FAIL: README.md says {wrong} tests; the suite collects {actual}.",
                f"       {len(declared)} count(s) found, {len(wrong)} wrong. Update every one.",
            ],
        )

    plural = "s" if len(declared) != 1 else ""
    return Result(
        ok=True,
        collected=actual,
        declared=declared,
        exempt=exempt,
        lines=[
            f"ok: README.md and the suite agree on {actual} tests "
            f"({len(declared)} mention{plural})"
        ],
    )
