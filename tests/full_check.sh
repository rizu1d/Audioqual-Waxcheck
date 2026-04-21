#!/bin/bash
# WaxCheck Full Verification
# Runs complete verification suite (~2-3min)
cd "$(dirname "$0")/.."

echo "=== WaxCheck Full Verification ==="
echo ""

python3 tests/verify_implementation.py --full
exit $?
