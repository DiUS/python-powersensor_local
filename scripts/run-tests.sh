#!/bin/bash
set -euo pipefail
rootdir="$(realpath "$(dirname "$0")/..")"
testsdir="${rootdir}/tests"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${rootdir}/src"
export PYTEST_COVERAGE_DATA_FILE="${testsdir}/.coverage"

extra=
[ -z "$@" ] && extra="--cov-fail-under=100"

echo "Linting tests..."
mypy --ignore-missing-imports "${testsdir}"

pytest \
  --cov=powersensor_local.xlatemsg \
  --cov-report term-missing \
  --cov-config="${testsdir}/.coveragerc" \
  --cache-clear \
  --capture=no \
  "${testsdir}" \
  "${extra}" \
  "$@"
