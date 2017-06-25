#!/bin/bash

set -e
set -u

CMD="python"
ARG1="${1:-}"

if [ "$ARG1" = '--coverage' ]; then
    CMD="coverage run -a --source ofp_app"
fi

echo "Test layer2 demo with unknown argument."
$CMD -m ofp_app.demo.layer2 --unknown-argument || true

echo "Test layer2 demo with simulator (count=50)"
$CMD -m ofp_app.demo.simulator \
        --listen-endpoints=6653 \
        --exit-timeout=3 \
        --simulator-count=50 \
        --loglevel=warning \
        ofp_app.demo.layer2

echo "Test conntest demo with simulator (count=10)"
$CMD -m ofp_app.demo.simulator \
        --listen-endpoints=6653 \
        --exit-timeout=3 \
        ofp_app.demo.conntest

exit 0
