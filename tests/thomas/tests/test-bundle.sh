#!/bin/sh
# Supply a wheel built from the independent trading checkout.
set -eu
wheel=${1:?Usage: test-bundle.sh /path/to/portfolio_advisory-*.whl}
tests=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
cp "$wheel" "$stage/"
set -- "/wheels/$(basename -- "$wheel")" "${2:-}"
if [ -n "$2" ]; then
    cp "$2" "$stage/"
    set -- "$1" "/wheels/$(basename -- "$2")"
else
    set -- "$1"
fi
docker build -t thomas-portability-runtime:local "${THOMAS_RUNTIME:?set THOMAS_RUNTIME to the host infrastructure/always-on checkout}"
docker build -t thomas-portability-test:local -f "$tests/Dockerfile" "$stage"
docker run --rm -i --read-only --network none --cap-drop ALL \
    --security-opt no-new-privileges --tmpfs /home/node:exec,uid=1000,gid=1000,mode=0700 \
    --tmpfs /tmp:mode=1777 --entrypoint python3 thomas-portability-test:local \
    - "$@" < "$tests/bundle.py"
