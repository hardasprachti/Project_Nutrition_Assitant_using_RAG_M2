#!/usr/bin/env bash
# Fails if anything that looks like a backend secret appears in the frontend source or its build output.
# The browser must only ever talk to our backend (Architecture §19).
set -euo pipefail

cd "$(dirname "$0")/../frontend"

patterns=(
  'sk-ant-[A-Za-z0-9_-]{10,}'     # Anthropic keys
  'sk-[A-Za-z0-9_-]{20,}'         # OpenAI-style keys
  'ANTHROPIC_API_KEY'
  'OPENAI_API_KEY'
  'DATABASE_URL'
  'ADMIN_TOKEN'
  'SUPABASE_SERVICE'
  'service_role'
  'postgres(ql)?(\+[a-z0-9]+)?://[^ "'"'"']+:[^ "'"'"']+@'   # connection strings with credentials
)
regex="$(IFS='|'; echo "${patterns[*]}")"

# Source and config always; the client bundle (.next/static) only if a build has been run.
# .next/server is framework code that never ships to the browser, so it is not scanned.
targets=(src package.json next.config.js)
[ -d .next/static ] && targets+=(.next/static)

if grep -rEn --exclude-dir=node_modules -e "$regex" "${targets[@]}"; then
  echo "ERROR: possible secret found in the frontend (see matches above)." >&2
  exit 1
fi
echo "OK: no secret patterns found in frontend (${targets[*]})."
