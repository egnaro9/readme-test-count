#!/usr/bin/env python3
"""Plant a wrong count in this repository's README and require the gate to notice.

The dogfood step passes on a correct repository, and would pass just as happily with the
comparison deleted, so on its own it proves only that the tool runs. This plants the defect
the tool exists to catch and requires a nonzero exit that names the planted number.

Written in Python rather than inline `sed -i`, because `sed -i` takes an argument on BSD and
not on GNU, so the inline version could only be tested on the runner. A step that cannot be
run locally is a step nobody runs until it breaks.

    python scripts/prove_the_gate_fails.py
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

PLANTED = "9999"
ROOT = pathlib.Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def main() -> int:
    original = README.read_text(encoding="utf-8")
    declared = original.count(" tests")
    if declared == 0:
        print("FAIL: README.md has no count to plant a defect in", file=sys.stderr)
        return 1

    mutated, n = re.subn(r"\b\d+ tests\b", f"{PLANTED} tests", original)
    if n == 0:
        print("FAIL: no declaration matched, so nothing was planted", file=sys.stderr)
        return 1

    try:
        README.write_text(mutated, encoding="utf-8")
        p = subprocess.run([sys.executable, "-m", "readme_test_count.cli", str(ROOT)],
                           capture_output=True, text=True)
    finally:
        README.write_text(original, encoding="utf-8")

    out = p.stdout + p.stderr
    print(out.strip())

    # An explicit comparison, never `!`, so a crash exiting 2 is not read as a detection.
    if p.returncode != 1:
        print(f"FAIL: planted {n} wrong count(s) and the gate exited {p.returncode}, wanted 1",
              file=sys.stderr)
        return 1
    if PLANTED not in out:
        print(f"FAIL: it failed, but never mentioned the planted {PLANTED}. The failure may "
              "have had nothing to do with the count.", file=sys.stderr)
        return 1

    print(f"\nok: planted {n} wrong count(s), the gate exited 1 and named {PLANTED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
