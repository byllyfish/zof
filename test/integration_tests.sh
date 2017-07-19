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
        --sim-timeout=3 \
        --sim-count=50 \
        --loglevel=info \
        --x-modules=ofp_app.demo.layer2

echo "Test conntest demo with simulator (count=10)"
$CMD -m ofp_app.demo.simulator \
        --listen-endpoints=6653 \
        --sim-timeout=3 \
        --x-modules=ofp_app.demo.conntest

echo "Test layer2 demo with simulator using TLS"
$CMD -m ofp_app.demo.simulator \
        --listen-endpoints=6653 \
        --listen-cert="$SCRIPT_DIR/ctl-cert.pem" \
        --listen-privkey="$SCRIPT_DIR/ctl-privkey.pem" \
        --listen-cacert="$SCRIPT_DIR/sw-cacert.pem" \
        --sim-timeout=3 \
        --sim-count=5 \
        --loglevel=info \
        --sim-cert="$SCRIPT_DIR/sw-cert.pem" \
        --sim-privkey="$SCRIPT_DIR/sw-privkey.pem" \
        --sim-cacert="$SCRIPT_DIR/ctl-cacert.pem" \
        --x-modules=ofp_app.demo.layer2

echo "Test layer2 demo with simulator using TLS (self-signed certs)"
# This test also tells the simulator to use multiple switch certificates.
$CMD -m ofp_app.demo.simulator \
        --listen-endpoints=6653 \
        --listen-cert="$SCRIPT_DIR/ss-cntl.cert" \
        --listen-privkey="$SCRIPT_DIR/ss-cntl.key" \
        --listen-cacert="$SCRIPT_DIR/ss-sw.cacert" \
        --sim-timeout=3 \
        --sim-count=5 \
        --loglevel=info \
        --sim-cert="$SCRIPT_DIR/ss-sw2.cert" \
        --sim-privkey="$SCRIPT_DIR/ss-sw2.key" \
        --sim-cacert="$SCRIPT_DIR/ss-cntl.cert" \
        --x-modules=ofp_app.demo.layer2 

exit 0
