#!/bin/bash

set -e

python -m pytest --pylint --pylint-error-types=WEF --pylint-rcfile=/dev/null \
                 --mypy \
                 --cov=zoflite --cov-report=term-missing --cov-fail-under=90

echo "===== pycodestyle ====="
pycodestyle zoflite

echo "===== pydocstyle ====="
pydocstyle zoflite
