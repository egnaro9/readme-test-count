# readme-test-count

Fail CI if your README's advertised test count disagrees with what pytest actually collects.

```bash
pip install readme-test-count
readme-test-count            # in your project root
```

> Not on PyPI until the first release runs. Until then:
> `pip install git+https://github.com/egnaro9/readme-test-count`
> Delete this note in the same commit that cuts the release, or it becomes the thing this
> tool exists to catch.

```
ok: README.md and the suite agree on 23 tests (2 mentions)
```

## Why

On 2026-10-07 I audited five of my own repositories. **All five advertised a stale test
count.** 42 where the suite collected 58, 45 where it collected 60, 97 where it collected
150. Every one of those numbers was true the day it was written, and nothing ever looked
again.

That is the same defect those repositories had just been audited for: a claim with no check
behind it. A number in a README is a test assertion that nobody runs.

## What it refuses to let pass

The interesting part is not the comparison, it is the four cases where a looser version
reports success:

| situation | what a looser check does | what this does |
|---|---|---|
| README states no count | passes, nothing to compare | **fails.** "Nothing to check" is how a check stops checking |
| `pytest --collect-only` errors | reads it as zero tests | **fails.** A collection with no number is an error, not a zero |
| README states the count twice | checks the first one | **fails** unless every occurrence matches |
| a test file collected nothing | passes, pytest reported no error | **fails.** See below |

That last one was learned hours after the rest shipped. A module opening with

```python
pytest.importorskip("some_optional_dep")
```

vanishes at collection with **no error and no mention**. pytest reports a collection of 58
and means it. An earlier version of this tool read that 58, agreed with a README that had
just been edited to match it, and would have frozen the wrong number in place. CI, which
installed the optional extra, collected 67.

So a count is only meaningful if the environment is complete, and the only evidence of
incompleteness is a file on disk that produced nothing. The tool compares the collection
against the filesystem, not just against your README.

A module that is genuinely meant to be skipped in this job says so in its own text:

```python
# readme-test-count: exempt, this needs the postgres service from the other CI job
```

Exemptions are printed on every run, including passing ones. An exemption nobody can see is
the same problem one level down.

## In CI

```yaml
      - run: pip install readme-test-count
      - name: README's advertised test count must match the suite
        run: readme-test-count
```

Install the same extras CI installs before this step, or it will correctly tell you the
environment is incomplete.

## The pattern, and its one real limitation

A declaration is `\b(\d+) tests\b`: a number followed by the plural word. That is deliberate,
so prose like "300 test claims from SciFact" is not mistaken for a claim about your suite.

The limitation follows directly: **you cannot write a historical count in the plural form.**
A sentence like "we shipped with 12 of them in 2023", written with the plural word in place
of "of them", reads as a declaration and this tool will object to it.

This README cannot show you that literal, because CI runs the tool on this README and it
would be rejected. Writing this section is what caught it: the first draft contained both
that example and a quoted "58 collected" from the section above, and the tool failed its own
repository on both. Drop the word or rephrase. That is the cost of a pattern simple enough to
explain in one line, and it is a cost I would rather pay than guess at intent.

## Options

```
readme-test-count [root] [--tests-dir DIR]
```

`root` defaults to the working directory. `--tests-dir` defaults to `tests` and is the
directory scanned for files that collected nothing.

## It checks itself

This repository's CI runs the tool on this repository, so the count at the top of this file
is enforced by the thing it describes. The suite is 23 tests and every documented failure
mode above has one, including the cases that only fail if the tool is working: a broken
collection must not read as zero, and a silently skipped module must not read as healthy.

## Where it came from

Extracted on 2026-10-09 from five repositories that each held a byte-identical copy
(`gradecore`, `deadgate`, `agent-graph`, `rag-eval-lab`, `mcp-tools`). Five copies and one
maintainer is a package that has not been written yet. A sibling script in two of those
repositories had already drifted into two different versions, which is what the sixth copy
of this one would have looked like in a few months.

MIT licensed.
