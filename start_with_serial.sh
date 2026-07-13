#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "${WYL_ASR_SERIAL_PORT:-}" ]; then
    export WYL_ASR_SERIAL_PORT="/dev/ttyUSB0"
fi

export WYL_ASR_ENABLE_SERIAL=1

cat <<EOF
Serial mode enabled.
  Port:     ${WYL_ASR_SERIAL_PORT}
  Baudrate: ${WYL_ASR_SERIAL_BAUDRATE:-9600}
EOF

if [ "$#" -eq 0 ]; then
    set -- start
fi
exec "$ROOT_DIR/start.sh" "$@"
