#!/usr/bin/env bash
set -euo pipefail

mkdir -p backup
for file in data/*.txt; do
  cp "$file" backup/
done
