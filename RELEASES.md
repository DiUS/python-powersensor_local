# Release process

This project publishes to PyPI in two stages: a release candidate on
TestPyPI first, then the same tagged version on production PyPI once it's
been verified. The goal is to never publish a version to production PyPI
that hasn't already been installed and exercised from TestPyPI.

## Overview

1. Cut a release candidate, publish it to TestPyPI, and tag it.
2. Test the TestPyPI package.
3. Optionally publish that same tag to production PyPI, to test against
   the real PyPI environment.
4. Once happy, cut the final release (same version, `rc*` suffix
   dropped), publish it to TestPyPI, and tag it.
5. Test again, then publish that tag to production PyPI.

Both the TestPyPI and production PyPI publish steps are only triggered
manually, from the **Release** workflow in GitHub Actions, and only run
from the `main` branch.

## Step by step

### 1. Cut a release candidate

- Bump `__version__` in
  [`src/powersensor_local/__init__.py`](src/powersensor_local/__init__.py)
  and append an `rc*` suffix, e.g. `2.2.1rc1`.
- Merge that change into `main`.

### 2. Publish the release candidate to TestPyPI

- Trigger the **Release** workflow from the GitHub Actions web interface.
- Select `test.pypi` as the publish destination.
- The workflow reads `__version__` straight out of `__init__.py` on
  `main`, builds the distribution, and publishes it to TestPyPI.
- On a successful publish, the workflow creates and pushes a git tag
  matching the version string (e.g. `v2.2.1rc1`).

### 3. Test the TestPyPI package

- Install the package from TestPyPI and verify it behaves as expected.

### 4. (Optional) Publish the release candidate to production PyPI

- If you want to test against the real PyPI environment before doing a
  final release, trigger the **Release** workflow again, this time
  selecting `pypi` as the destination and entering the tag created in
  step 2 (e.g. `v2.2.1rc1`).
- The workflow checks out that exact tag, builds from it, and publishes
  to PyPI. It does **not** create a tag in this path, since the tag
  already exists from step 2.

### 5. Finalise the release

- Once you're happy with the release candidate, remove the `rc*` suffix
  from `__version__` (e.g. `2.2.1rc1` → `2.2.1`) and merge into `main`.
- Repeat steps 2–3: publish to TestPyPI, which tags the final version
  (e.g. `v2.2.1`), and test that package.
- Publish that tag to production PyPI the same way as step 4, using the
  final tag this time. This is the real release.

## Rationale

- **TestPyPI before PyPI**: PyPI (and TestPyPI) reject re-uploading a
  filename that's already been published — there's no way to overwrite
  or delete a bad upload. Requiring every version to land on TestPyPI
  first, and be tested there, catches packaging problems (missing
  files, bad metadata, broken entry points, etc.) before they can burn a
  version number on production PyPI.
- **Publishing the exact same tag to both indexes**: TestPyPI and PyPI
  are independent indexes, so the same version string can be published
  to both. Releasing to PyPI always checks out a tag that was already
  built and validated via the TestPyPI path, rather than rebuilding from
  a moving branch tip, so what you tested is what ships.
- **Tagging only happens after a successful TestPyPI publish**: this
  keeps a pushed tag meaningful — if the TestPyPI publish fails (for
  example, because the version wasn't bumped and the filename already
  exists), no tag is created and nothing needs to be cleaned up. The
  production PyPI publish step never creates a tag, since by
  construction the tag already exists from the TestPyPI step; this
  avoids ever trying to recreate/move an existing tag.
- **`main`-only restriction**: publishing (to either index) is only
  allowed when the workflow is triggered from `main`, so every published
  version corresponds to a real, reviewed commit on the trunk branch,
  never an untested feature branch.
- **`rc*` suffix**: using a
  [PEP 440](https://peps.python.org/pep-0440/#pre-releases) pre-release
  suffix means `pip install powersensor-local` never resolves to a
  release candidate by accident — installers only pick up an `rc`
  version if you explicitly ask for it (`pip install --pre` or an exact
  version pin). It also keeps release candidates and final releases as
  distinct, individually addressable versions on both indexes.
