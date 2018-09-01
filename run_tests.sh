#!/bin/bash
#
# Run tests with code coverage.
#
# Also run the following lint checks:
#   - pylint (warning, error, failure)
#   - mypy
#   - pycodestyle
#   - pydocstyle
#   - pytype

set -eu

PYLINT_ARGS="--pylint-error-types=WEF --pylint-rcfile=/dev/null"
COVERAGE_ARGS="--cov-report=term-missing --cov-fail-under=95"

python -m pytest -s -vv --timeout=30 \
                 --pylint $PYLINT_ARGS \
                 --mypy \
                 --cov=zof $COVERAGE_ARGS

echo "===== pytype ====="
pytype zof

echo "===== pycodestyle ====="
pycodestyle zof tests demo

echo "===== pydocstyle ====="
pydocstyle zof tests

