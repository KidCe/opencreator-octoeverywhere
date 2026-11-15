#!/bin/sh
# Run after oc-plugin install --no-restart, using OpenCreator's native Python.
set -eu
plugin_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec nice -n 10 /usr/data/python-hf/bin/python3.13 "$plugin_dir/scripts/setup_runtime.py" "$@"
