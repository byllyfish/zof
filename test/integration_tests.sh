#!/bin/bash

set -e
set -u

CMD="python"
ARG1="${1:-}"
SCRIPT_DIR=`dirname "$0"`

if [ "$ARG1" = '--coverage' ]; then
    CMD="coverage run -a --source zof"
fi

echo "Test layer2 demo with unknown argument."
$CMD -m zof.demo.layer2 --unknown-argument || true

echo "Test layer2 with invalid oftr argument"
$CMD -m zof.demo.layer2 --x-oftr-args='trace=rpc' &> log.txt || true
grep "ClosedException" log.txt

echo "Test layer2 demo help."
$CMD -m zof.demo.layer2 --help | grep "show this help message and exit"

echo "Test layer2 demo with simulator (count=50)"
$CMD -m zof.demo.simulator \
        --listen-endpoints=6653 \
        --sim-timeout=3 \
        --sim-count=50 \
        --loglevel=info \
        --x-modules=zof.demo.layer2

echo "Test conntest demo with simulator (count=10)"
$CMD -m zof.demo.simulator \
        --listen-endpoints=6653 \
        --sim-timeout=3 \
        --x-modules=zof.demo.conntest

echo "Test layer2 demo with simulator using TLS"
$CMD -m zof.demo.simulator \
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
        --x-modules=zof.demo.layer2

echo "Test layer2 demo with simulator using TLS (self-signed certs)"
# This test also tells the simulator to use multiple switch certificates.
$CMD -m zof.demo.simulator \
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
        --x-modules=zof.demo.layer2 

echo "Test table_features demo with simulator (1 multipart reply)"
$CMD -m zof.demo.simulator \
        --listen-endpoints=6653 \
        --sim-count=1 \
        --x-modules=zof.demo.table_features &> /dev/null

exit 0
