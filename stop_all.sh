#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$#" -eq 0 ]; then
    set -- stop
fi
exec "$ROOT_DIR/start.sh" "$@"
