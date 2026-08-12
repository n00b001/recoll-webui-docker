#!/bin/bash
# Verify recoll-engine/entrypoint.sh path-variable defaults behave correctly
# in the environment docker-compose actually provides (no *_PATH vars injected).
# Usage: bash recoll-engine/test_entrypoint_env.sh  (run from repo root)
set -euo pipefail

ENTRYPOINT="${1:-recoll-engine/entrypoint.sh}"
TEMPLATE="${2:-recoll-engine/recoll.conf.template}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/root/.recoll"
cp "$TEMPLATE" "$TMP/recoll.conf.template"

# Extract ONLY the defaulting lines under test (export VAR="${VAR:-container/path}")
grep -E '^export (ALEX|CHLOE|MBSYNC|WHATSAPP|SMS)_' "$ENTRYPOINT" > "$TMP/env.sh"
bash -n "$TMP/env.sh"
test -s "$TMP/env.sh" || { echo "FAIL: no default lines found in entrypoint"; exit 1; }

cat > "$TMP/render.sh" <<'EOF'
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
# docker-compose injects NO *_PATH vars on recoll-engine (they only exist on the host)
unset ALEX_HADDES_PATH ALEX_PHONE_PATH ALEX_GDRIVE_PATH ALEX_GPHOTOS_PATH
unset CHLOE_HOME_SYNC_PATH CHLOE_PHONE_PATH CHLOE_GDRIVE_PATH CHLOE_GPHOTOS_PATH
unset MBSYNC_DATA_PATH WHATSAPP_DATA_PATH SMS_DATA_PATH
set -a
source env.sh
set +a
envsubst '${ALEX_HADDES_PATH} ${ALEX_PHONE_PATH} ${ALEX_GDRIVE_PATH} ${ALEX_GPHOTOS_PATH} \
${CHLOE_HOME_SYNC_PATH} ${CHLOE_PHONE_PATH} ${CHLOE_GDRIVE_PATH} ${CHLOE_GPHOTOS_PATH} \
${MBSYNC_DATA_PATH} ${WHATSAPP_DATA_PATH} ${SMS_DATA_PATH}' \
  < recoll.conf.template > root/.recoll/recoll.conf

# With no vars set, topdirs must still resolve to the container mount paths.
grep -q '^topdirs = /homes/alex/hades /homes/alex/phone /homes/alex/gdrive /homes/alex/gphotos' root/.recoll/recoll.conf \
  || { echo "FAIL: topdirs did not resolve to container /homes/* paths:"; grep '^topdirs' root/.recoll/recoll.conf; exit 1; }
# No ${VAR} placeholders may survive.
if grep -q '\${' root/.recoll/recoll.conf; then
  echo "FAIL: unresolved template vars in rendered recoll.conf:"; grep '\${' root/.recoll/recoll.conf; exit 1
fi
echo "PASS: entrypoint renders recoll.conf with container paths, no env vars required"
EOF
bash -n "$TMP/render.sh"
bash "$TMP/render.sh"

# When a var IS provided in-container, it must override the default.
ALEX_HADDES_PATH=/custom/override bash -c '
  set -euo pipefail
  src=/dev/stdin
  . <(grep -E "^export (ALEX|CHLOE|MBSYNC|WHATSAPP|SMS)_" "$1")
  [ "$ALEX_HADDES_PATH" = "/custom/override" ] || { echo "FAIL: override not honored"; exit 1; }
' _ "$ENTRYPOINT"
echo "PASS: in-container override of ALEX_HADDES_PATH is honored"
echo "ALL PASS"