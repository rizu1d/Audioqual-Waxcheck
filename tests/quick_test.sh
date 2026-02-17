#!/bin/bash
cd "$(dirname "$0")/.."
python tests/run_tests.py --summary
