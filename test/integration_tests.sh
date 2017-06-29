#!/bin/bash

set -e
set -u

CMD="python"
ARG1="${1:-}"
SCRIPT_DIR=`dirname "$0"`

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

echo "Test layer2 demo with simulator using TLS"
$CMD -m ofp_app.demo.simulator \
        --listen-endpoints=6653 \
        --cert="$SCRIPT_DIR/ctl-cert.pem" \
        --privkey="$SCRIPT_DIR/ctl-privkey.pem" \
        --cacert="$SCRIPT_DIR/sw-cacert.pem" \
        --exit-timeout=3 \
        --simulator-count=5 \
        --loglevel=info \
        --sim-cert="$SCRIPT_DIR/sw-cert.pem" \
        --sim-privkey="$SCRIPT_DIR/sw-privkey.pem" \
        --sim-cacert="$SCRIPT_DIR/ctl-cacert.pem" \
        ofp_app.demo.layer2

exit 0
