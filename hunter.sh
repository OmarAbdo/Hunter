#!/usr/bin/env sh
# Runs Hunter from this folder with the project's own environment (.venv, built by doctrine check
# from requirements.lock). Usage: ./hunter.sh discover, ./hunter.sh boards add <link>.
here=$(cd "$(dirname "$0")" && pwd)
python="$here/.venv/Scripts/python.exe"
[ -x "$python" ] || python="$here/.venv/bin/python"
if [ ! -x "$python" ]; then
    echo "Hunter's environment isn't built yet: run \"doctrine check\" once in $here" >&2
    exit 1
fi
cd "$here" && PYTHONPATH="$here/src" exec "$python" -m hunter "$@"
