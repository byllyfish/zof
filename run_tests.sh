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
COVERAGE_ARGS="--cov-report=term-missing --cov-fail-under=90"

python -m pytest -s -vv --timeout=30 --durations=5 \
                 --pylint $PYLINT_ARGS \
                 --mypy \
                 --cov=zof $COVERAGE_ARGS \
                 zof tests demo

echo "===== pytype ====="
pytype zof || true

echo "===== pycodestyle ====="
pycodestyle --max-line-length=95 zof tests demo

echo "===== pydocstyle ====="
pydocstyle zof tests
