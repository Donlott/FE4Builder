#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
exec python3 FE4Builder/scripts/start.py "$@"
