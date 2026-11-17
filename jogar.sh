#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"
mkdir -p logs state
export PYTHONPATH="$PWD/vendor"
export PYTHONUNBUFFERED=1
exec flock --nonblock --no-fork state/game.lock python3 src/play.py >>logs/game.log 2>&1
