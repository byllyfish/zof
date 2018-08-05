#!/bin/bash

set -e

python -m pytest --pylint --pylint-error-types=EF \
                 --mypy \
                 --cov=zoflite --cov-report=term-missing --cov-fail-under=90

pycodestyle zoflite
pydocstyle zoflite
