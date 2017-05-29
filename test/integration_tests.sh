#!/bin/bash


CMD="python"

if [ "$1" = '--coverage' ]; then
    CMD="coverage run -a --source pylibofp"
fi

echo "Test layer2 demo with unknown argument."
$CMD -m pylibofp.demo.layer2 --unknown-argument

echo "Test layer2 demo with simulator (count=50)"
$CMD -m pylibofp.demo.simulator \
        --listen-endpoints=6653 \
        --exit-timeout=3 \
        --simulator-count=50 \
        --loglevel=warning \
        pylibofp.demo.layer2

exit 0
