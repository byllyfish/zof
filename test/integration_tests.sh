#!/bin/bash


CMD="python"

if [ "$1" = '--coverage' ]; then
    CMD="coverage run -a --source ofp_app"
fi

echo "Test layer2 demo with unknown argument."
$CMD -m ofp_app.demo.layer2 --unknown-argument

echo "Test layer2 demo with simulator (count=50)"
$CMD -m ofp_app.demo.simulator \
        --listen-endpoints=6653 \
        --exit-timeout=3 \
        --simulator-count=50 \
        --loglevel=warning \
        ofp_app.demo.layer2

exit 0
