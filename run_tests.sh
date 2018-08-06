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
COVERAGE_ARGS="--cov-report=term-missing --cov-fail-under=90"

python -m pytest -s -v --timeout=10 \
                 --pylint $PYLINT_ARGS \
                 --mypy \
                 --cov=zoflite $COVERAGE_ARGS

echo "===== pycodestyle ====="
pycodestyle zoflite

echo "===== pydocstyle ====="
pydocstyle zoflite

echo "===== pytype ====="
pytype zoflite
