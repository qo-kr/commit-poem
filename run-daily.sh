#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# The daily edition covers yesterday in Korea, regardless of the cron host timezone.
export TZ=Asia/Seoul

IFS=: read -r -a roots <<< "${COMMITPOEM_LOCAL_ROOTS:-${HOME}/genideas-labs:${HOME}/work-oq:/mnt/ssd4tb/genideas-secure-labs:/mnt/ssd4tb/k-gen-food}"
local_args=()
for root in "${roots[@]}"; do
  if [[ -d "$root" ]]; then
    local_args+=(--local-root "$root")
  else
    printf 'Local repository root is missing: %s\n' "$root" >&2
  fi
done
if [[ ${#local_args[@]} -eq 0 ]]; then
  printf 'No local repository roots available; refusing to fall back to organization-wide API collection.\n' >&2
  exit 1
fi

.venv/bin/commitpoem \
  "${local_args[@]}" \
  --update-main \
  --org qo-kr \
  --org genideas-secure-labs \
  --org k-gen-food \
  --since "$(date -d 'yesterday 00:00:00' +%Y-%m-%dT%H:%M:%S%:z)" \
  --until "$(date -d 'yesterday 23:59:59' +%Y-%m-%dT%H:%M:%S%:z)"
