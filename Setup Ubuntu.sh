#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
command -v apt-get >/dev/null 2>&1 || { echo "This setup targets Ubuntu/Debian. See LINUX.md." >&2; exit 1; }
sudo apt-get update
sudo apt-get install -y python3 python3-tk python3-venv xvfb xauth
python3 -c 'import sys,tkinter; assert sys.version_info >= (3,10), "Python 3.10+ is required"'
printf '\nSetup complete. Run: sh Launcher.sh\nOptional audio setup is documented in LINUX.md.\n'
