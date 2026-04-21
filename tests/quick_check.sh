#!/bin/bash
# WaxCheck Quick Check
# Runs quick verification + algorithm tests (~30s)
cd "$(dirname "$0")/.."

echo "=== WaxCheck Quick Check ==="
echo ""

python3 tests/verify_implementation.py --quick
QUICK=$?

echo ""
echo "--- Algorithm Tests ---"
python3 tests/run_tests.py --summary
ALGO=$?

echo ""
if [ $QUICK -eq 0 ] && [ $ALGO -eq 0 ]; then
    echo "RESULTADO: TODO OK"
    exit 0
else
    echo "RESULTADO: FALLOS DETECTADOS"
    exit 1
fi
