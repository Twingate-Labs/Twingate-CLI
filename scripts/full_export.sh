#!/usr/bin/env bash
#
# full_export.sh — Export an entire Twingate tenant to CSV and JSON files.
#
# Usage:
#   ./scripts/full_export.sh                     # uses default tgcli session
#   ./scripts/full_export.sh -s MySession        # uses a named session
#   ./scripts/full_export.sh -o ./customer-acme  # custom output directory
#
# Prerequisites:
#   1. pip install -e .   (from the repo root)
#   2. tgcli auth login -a <API_KEY> -t <tenant>

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
SESSION_FLAG=""
OUTPUT_DIR=""

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--session) SESSION_FLAG="-s $2"; shift 2 ;;
        -o|--output)  OUTPUT_DIR="$2";      shift 2 ;;
        -h|--help)
            echo "Usage: $0 [-s session_name] [-o output_dir]"
            echo ""
            echo "Options:"
            echo "  -s, --session   tgcli session name (from 'tgcli auth login -s ...')"
            echo "  -o, --output    output directory (default: export_<tenant>_<date>)"
            echo "  -h, --help      show this help"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Resolve tenant name for the output directory ──────────────────────────────
if command -v tgcli &>/dev/null; then
    TENANT=$(tgcli $SESSION_FLAG auth list 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list) and data:
        print(data[0].get('tenant', 'unknown'))
    elif isinstance(data, dict):
        print(data.get('tenant', 'unknown'))
    else:
        print('unknown')
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")
else
    echo "ERROR: tgcli not found. Install with: pip install -e ."
    exit 1
fi

if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="export_${TENANT}_$(date +%Y-%m-%d)"
fi

mkdir -p "$OUTPUT_DIR/csv" "$OUTPUT_DIR/json"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            Twingate Full Tenant Export                      ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Tenant:    $TENANT"
echo "║  Output:    $OUTPUT_DIR/"
echo "║  Date:      $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Helper ────────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
TOTAL=0

run_export() {
    local label="$1"
    shift
    local cmd=("$@")
    TOTAL=$((TOTAL + 1))

    printf "  %-35s" "$label..."
    if "${cmd[@]}" > /dev/null 2>&1; then
        echo "✓"
        PASS=$((PASS + 1))
    else
        echo "✗ (failed)"
        FAIL=$((FAIL + 1))
    fi
}

export_entity() {
    local name="$1"
    local command="$2"
    local subcommand="${3:-list}"

    run_export "$name (CSV)" \
        bash -c "tgcli $SESSION_FLAG -f CSV $command $subcommand > \"$OUTPUT_DIR/csv/${name}.csv\""

    run_export "$name (JSON)" \
        bash -c "tgcli $SESSION_FLAG -f JSON $command $subcommand > \"$OUTPUT_DIR/json/${name}.json\""
}

# ── Entity exports ────────────────────────────────────────────────────────────
echo "Exporting entities..."
echo ""

export_entity "resources"        "resource"
export_entity "users"            "user"
export_entity "groups"           "group"
export_entity "devices"          "device"
export_entity "connectors"       "connector"
export_entity "remote_networks"  "network"
export_entity "service_accounts" "account"
export_entity "security_policies" "policy"
export_entity "serial_numbers"   "device snumber"

echo ""
echo "Exporting DNS security..."
echo ""

run_export "dns_security (CSV)" \
    bash -c "tgcli $SESSION_FLAG -f CSV dnssec show > \"$OUTPUT_DIR/csv/dns_security.csv\""
run_export "dns_security (JSON)" \
    bash -c "tgcli $SESSION_FLAG -f JSON dnssec show > \"$OUTPUT_DIR/json/dns_security.json\""

echo ""
echo "Exporting relationship mappings..."
echo ""

run_export "user_network_map (CSV)" \
    bash -c "tgcli $SESSION_FLAG -f CSV mappings user-network > \"$OUTPUT_DIR/csv/user_network_map.csv\""
run_export "user_network_map (JSON)" \
    bash -c "tgcli $SESSION_FLAG -f JSON mappings user-network > \"$OUTPUT_DIR/json/user_network_map.json\""

run_export "resource_connectivity (CSV)" \
    bash -c "tgcli $SESSION_FLAG -f CSV mappings resource-connectivity > \"$OUTPUT_DIR/csv/resource_connectivity.csv\""
run_export "resource_connectivity (JSON)" \
    bash -c "tgcli $SESSION_FLAG -f JSON mappings resource-connectivity > \"$OUTPUT_DIR/json/resource_connectivity.json\""

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Export complete: $PASS/$TOTAL succeeded"
if [[ $FAIL -gt 0 ]]; then
    echo "  ⚠ $FAIL export(s) failed — check API key permissions"
fi
echo ""
echo "  CSV files:  $OUTPUT_DIR/csv/"
echo "  JSON files: $OUTPUT_DIR/json/"
echo ""

# Show file sizes
echo "  File sizes:"
for f in "$OUTPUT_DIR/csv/"*.csv "$OUTPUT_DIR/json/"*.json; do
    if [[ -f "$f" ]]; then
        size=$(wc -c < "$f" | tr -d ' ')
        if [[ $size -gt 1048576 ]]; then
            printf "    %-40s %s MB\n" "$(basename "$f")" "$(echo "scale=1; $size/1048576" | bc)"
        elif [[ $size -gt 1024 ]]; then
            printf "    %-40s %s KB\n" "$(basename "$f")" "$(echo "scale=1; $size/1024" | bc)"
        else
            printf "    %-40s %s B\n" "$(basename "$f")" "$size"
        fi
    fi
done
echo "════════════════════════════════════════════════════════════════"
