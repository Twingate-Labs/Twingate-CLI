#!/usr/bin/env bash
#
# Disable every Resource that mappings resource-connectivity flags as
# offline (no live Connector in its Remote Network).
#
# Usage:
#   ./disable_offline_resources.sh <session>              # dry run (default)
#   ./disable_offline_resources.sh <session> --execute     # actually disable them
#
set -euo pipefail

SESSION="${1:?Usage: $0 <session> [--execute]}"
MODE="${2:-}"

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required but not installed." >&2
  exit 1
fi

echo "Fetching offline resources for session: $SESSION"
OFFLINE_JSON=$(tgcli -s "$SESSION" mappings resource-connectivity --offline-only)

COUNT=$(echo "$OFFLINE_JSON" | jq 'length')

if [ "$COUNT" -eq 0 ]; then
  echo "No offline resources found. Nothing to do."
  exit 0
fi

echo ""
echo "Found $COUNT offline resource(s):"
echo "$OFFLINE_JSON" | jq -r '.[] | "  \(."resource.id")  \(."resource.name")  (remoteNetwork: \(."remoteNetwork.name"))"'

if [ "$MODE" != "--execute" ]; then
  echo ""
  echo "*** DRY RUN — no resources will be disabled. Re-run with --execute to apply. ***"
  exit 0
fi

echo ""
echo "Disabling $COUNT resource(s)..."
echo "$OFFLINE_JSON" | jq -r '.[] | ."resource.id"' | while read -r id; do
  echo "  disabling: $id"
  tgcli -s "$SESSION" resource disable -i "$id"
done

echo ""
echo "Done."
