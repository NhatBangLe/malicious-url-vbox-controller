#!/bin/bash

# --- Default Infrastructure Settings ---
VBOX_PATH="C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe"
VM_NAME="Win7-Pro-x64"
USER="admin"
PASS="admin"
SNAPSHOT="Base"
SCRIPT_PATH="C:\\Users\\admin\\Desktop\\script"
BASE_HOST_PATH="./Audit_Results"
RUN_HEADLESS=false
SOURCE_API_KEY=<your-api-key>
SOURCE=abuse
SOURCE_FETCH_MODE=past_30days

# --- Default Audit & Performance Settings ---
MAX_URL=1
DURATION=30
GUEST_OUTPUT="Z:\\"
IFACE=4 # Adjust based on your Wireshark configuration

# --- Optional Tool Paths & Configurations ---
# EXECUTION_TIMEOUT=300
# BOOT_TIMEOUT=300
# REG_PATH="C:\\script\\regview\\regview.exe"
# PROCMON_PATH="C:\\script\\procmon\\Procmon.exe"
# TSHARK_PATH="C:\\Program Files\\Wireshark\\tshark.exe"
# TSHARK_FIELDS="frame.number frame.time frame.len ip.src ip.dst tcp.srcport tcp.dstport http.request.method http.request.uri"

# --- Colors for Terminal ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

usage() {
    echo -e "${YELLOW}Usage:${NC} $0 [options]"
    echo ""
    echo "Options:"
    echo "  --source [string]                 Source for malicious URLs (default: "abuse"). Supported: abuse"
    echo "  --api-key [string]                (Optional) API key for fetching malicious URLs from your source."
    echo "  --fetch-mode [string]             Mode for fetching malicious URLs (default: "past30"). Supported: past30, only_active"
    echo "  --max-url [number]                Maximum number of URLs to audit. (audits all if omitted)"
    echo "  --duration [sec]                  Audit time per instance (default: 30)"
    echo "  --execution-timeout [sec]         Max time to wait for guest script execution (default: 300)"
    echo "  --boot-timeout [sec]              Wait time for OS boot (default: 300)"
    echo "  --vbox-path [path]                Path to VBoxManage executable"
    echo "  --snapshot [name]                 Snapshot to clone"
    echo "  --host-path [path]                Host directory for logs"
    echo "  --iface [number]                  Network interface number for tshark (default: 4)"
    echo "  --fields \"f1 f2\"                TShark fields to export"
    echo ""
    exit 1
}

# 1. Basic Argument Check
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then usage; fi

URL=$1
shift 

# 2. Parse Options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --fetch-mode) SOURCE_FETCH_MODE="$2"; shift ;;
        --source) SOURCE="$2"; shift ;;
        --api-key) SOURCE_API_KEY="$2"; shift ;;
        --max-url) MAX_URL="$2"; shift ;;
        --duration) DURATION="$2"; shift ;;
        --execution-timeout) EXECUTION_TIMEOUT="$2"; shift ;;
        --boot-timeout) BOOT_TIMEOUT="$2"; shift ;;
        --vbox-path) VBOX_PATH="$2"; shift ;;
        --snapshot) SNAPSHOT="$2"; shift ;;
        --host-path) BASE_HOST_PATH="$2"; shift ;;
        --fields) TSHARK_FIELDS="$2"; shift ;;
        *) echo -e "${RED}Unknown parameter:${NC} $1"; usage ;;
    esac
    shift
done

# 3. Pre-flight Checks
if [[ ! -f "main.py" ]]; then
    echo -e "${RED}Error:${NC} main.py not found in current directory."
    exit 1
fi

echo -e "${GREEN}Preparing Orchestration...${NC}"

# 4. Construct Command Array
CMD_ARGS=(
    python main.py
    --vbox-path "$VBOX_PATH"
    --vm "$VM_NAME"
    --user "$USER"
    --password "$PASS"
    --snapshot "$SNAPSHOT"
    --script-path "$SCRIPT_PATH"
    --base-host-path "$BASE_HOST_PATH"
    --duration "$DURATION"
    --output "$GUEST_OUTPUT"
    --iface "$IFACE"
)

# Optional arguments added only if they are set
if [[ -n "$BOOT_TIMEOUT" ]]; then
    CMD_ARGS+=(--boot-timeout "$BOOT_TIMEOUT")
fi

if [[ -n "$EXECUTION_TIMEOUT" ]]; then
    CMD_ARGS+=(--execution-timeout "$EXECUTION_TIMEOUT")
fi

if [[ -n "$MAX_URL" ]]; then
    CMD_ARGS+=(--max-url "$MAX_URL")
fi

if [[ -n "$SOURCE" ]]; then
    CMD_ARGS+=(--source "$SOURCE")
fi

if [[ -n "$SOURCE_FETCH_MODE" ]]; then
    CMD_ARGS+=(--fetch-mode "$SOURCE_FETCH_MODE")
fi

if [[ -n "$SOURCE_API_KEY" ]]; then
    CMD_ARGS+=(--api-key "$SOURCE_API_KEY")
fi

if [ "$RUN_HEADLESS" = true ]; then
    CMD_ARGS+=(--headless)
fi

if [[ -n "$TSHARK_FIELDS" ]]; then
    CMD_ARGS+=(--tshark-fields $TSHARK_FIELDS)
fi

if [[ -n "$TSHARK_PATH" ]]; then
    CMD_ARGS+=(--tshark-path $TSHARK_PATH)
fi

if [[ -n "$REG_PATH" ]]; then
    CMD_ARGS+=(--reg-path $REG_PATH)
fi

if [[ -n "$PROCMON_PATH" ]]; then
    CMD_ARGS+=(--procmon-path $PROCMON_PATH)
fi
# Optional arguments added only if they are set

# 5. Execute
"${CMD_ARGS[@]}"

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}Orchestrator finished successfully.${NC}"
else
    echo -e "\n${RED}Orchestrator exited with an error.${NC}"
fi