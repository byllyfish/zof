#!/bin/bash

set -e

python -m pytest --pylint --pylint-error-types=EF \
                 --mypy \
                 --cov=zoflite --cov-report=term-missing
