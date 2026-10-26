#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
sudo apt-get update
sudo apt-get install -y python3 python3-tk python3-venv
python3 -m venv .venv-linux
.venv-linux/bin/python -m pip install -r requirements.txt
printf '\nStudio setup complete. Run: sh "Start Studio.sh"\n'
