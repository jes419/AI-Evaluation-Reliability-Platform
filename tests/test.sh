#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
exec python -m pytest -q tests/unit tests/persistence tests/integration
