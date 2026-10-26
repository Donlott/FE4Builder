#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
if [ ! -x .venv-linux/bin/python ]; then
    echo 'Run sh "Setup Ubuntu.sh" first.' >&2
    exit 1
fi
exec .venv-linux/bin/python fe4_modding_studio/studio.py "$@"
