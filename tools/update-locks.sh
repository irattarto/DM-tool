#!/usr/bin/env sh
# Regenerates the hashed lock files the release builds install from (pip --require-hashes).
# Edit requirements.txt (the human-readable list), run this, review the diff, commit all three.
# Needs: pip install uv
set -eu
cd "$(dirname "$0")/.."
uv pip compile requirements-build.in --python-version 3.12 --python-platform windows \
    --generate-hashes --no-header -o requirements-windows.lock
uv pip compile requirements-build.in --python-version 3.12 --python-platform x86_64-manylinux_2_35 \
    --generate-hashes --no-header -o requirements-linux.lock
echo "Updated requirements-windows.lock and requirements-linux.lock"
