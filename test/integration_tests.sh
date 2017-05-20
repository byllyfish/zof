#!/bin/bash


COV=""

if [ "$1" = '--coverage' ]; then
    COV="coverage run --source pylibofp"
fi

echo "Test layer2 demo with unknown argument."
$COV python -m pylibofp.demo.layer2 --unknown-argument

echo "Test layer2 demo with simulator (count=50)"
$COV python -m pylibofp.service.simulator \
        --exit-timeout=3 \
        --simulator-count=50 \
        --loglevel=warning \
        pylibofp.demo.layer2.layer2

exit 0
