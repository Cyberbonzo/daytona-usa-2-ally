#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"
mkdir -p logs
export PYTHONPATH="$PWD/vendor"
export PYTHONUNBUFFERED=1
exec python3 src/play.py >>logs/game.log 2>&1
