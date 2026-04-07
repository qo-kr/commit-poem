#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

.venv/bin/commitpoem \
  --org qo-kr \
  --since "$(date -d yesterday +%Y-%m-%dT00:00:00Z)" \
  --until "$(date +%Y-%m-%dT00:00:00Z)"
