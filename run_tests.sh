#!/bin/bash
#
# Run tests with code coverage. All tests have a timeout of 30 seconds.
#
# Also run the following lint checks:
#   - pylint (warning, error, failure)
#   - mypy
#   - pycodestyle
#   - pydocstyle
#   - pytype

set -e

PYLINT_ARGS="--pylint-error-types=WEF --pylint-rcfile=/dev/null"
COVERAGE_ARGS="--cov-report=term-missing --cov-fail-under=95"

python -m pytest -s -vv --timeout=30 \
                 --pylint $PYLINT_ARGS \
                 --mypy \
                 --cov=zof $COVERAGE_ARGS

echo "===== pytype ====="
pytype zof || exit 0

echo "===== pycodestyle ====="
pycodestyle zof tests demo

echo "===== pydocstyle ====="
pydocstyle zof tests
