#!/usr/bin/env bash
set -euo pipefail

for file in data/*.txt; do
  cp "$file" backup/
done
