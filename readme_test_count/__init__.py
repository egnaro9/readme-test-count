"""Fail if README.md's advertised test count disagrees with the suite."""

from readme_test_count.core import (
    DEFAULT_TESTS_DIR,
    CollectionError,
    Result,
    collect,
    evaluate,
    silent_empty_test_files,
)

__all__ = [
    "CollectionError",
    "DEFAULT_TESTS_DIR",
    "Result",
    "collect",
    "evaluate",
    "silent_empty_test_files",
]
__version__ = "0.1.0"
