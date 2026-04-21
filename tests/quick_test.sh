#!/bin/bash
cd "$(dirname "$0")/.."
python3 tests/run_tests.py --summary
