"""Command line entry point.

The pre-extraction version resolved the project root from `__file__.parent.parent`, which
only worked because the script lived in `<root>/scripts/`. A packaged tool cannot know that,
so the root is an argument and defaults to the working directory.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from readme_test_count.core import DEFAULT_TESTS_DIR, evaluate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="readme-test-count",
        description="Fail if README.md's advertised test count disagrees with the suite.",
    )
    ap.add_argument("root", nargs="?", default=".",
                    help="project root holding README.md (default: the working directory)")
    ap.add_argument("--tests-dir", default=DEFAULT_TESTS_DIR,
                    help=f"directory scanned for test files that collected nothing "
                         f"(default: {DEFAULT_TESTS_DIR})")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL: {args.root} is not a directory", file=sys.stderr)
        return 1

    result = evaluate(root, tests_dir=args.tests_dir)
    if result.exempt:
        print(f"note: {len(result.exempt)} test file(s) exempt by declaration and NOT "
              f"counted: " + ", ".join(result.exempt))
    stream = sys.stdout if result.ok else sys.stderr
    for line in result.lines:
        print(line, file=stream)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
