#!/bin/bash
set -e
cd "$(dirname "$0")"
python -m worker.main
