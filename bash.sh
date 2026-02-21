#!/bin/bash

# --- Default Infrastructure Settings ---
VBOX_PATH="C:\\Program Files\\Oracle\\VirtualBox\\VBoxManage.exe"
VM_NAME="Win10"
USER="admin"
PASS=""
SNAPSHOT="Ready_Run_Audit"
VENV_PATH="C:\\Users\\admin\\Desktop\\tools\\malicious-url-monitor\\.venv"
GUEST_SCRIPT="C:\\Users\\admin\\Desktop\\tools\\malicious-url-monitor\\main.py"
BASE_HOST_PATH="./Audit_Results"
PARALLEL=1

# --- Default Audit & Performance Settings ---
DURATION=30
BOOT_TIMEOUT=300
GUEST_OUTPUT="Z:\\"
IFACE=4
REG_PATH="C:\\Users\\admin\\Desktop\\tools\\registry\\RegistryChangesView.exe"
PROCMON_PATH="C:\\Users\\admin\\Desktop\\tools\\procmon\\Procmon.exe"
TSHARK_PATH="C:\\Program Files\\Wireshark\\tshark.exe"
TSHARK_FIELDS="frame.number frame.time frame.len ip.src ip.dst tcp.srcport tcp.dstport http.request.method http.request.uri"

# --- Colors for Terminal ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

usage() {
    echo -e "${YELLOW}Usage:${NC} $0 [url] [options]"
    echo ""
    echo "Options:"
    echo "  --parallel [int]       Number of instances (default: 1)"
    echo "  --duration [sec]       Audit time per instance (default: 30)"
    echo "  --boot-timeout [sec]   Wait time for OS boot (default: 300)"
    echo "  --vbox-path [path]     Path to VBoxManage executable"
    echo "  --snapshot [name]      Snapshot to clone"
    echo "  --host-path [path]     Host directory for logs"
    echo "  --fields \"f1 f2\"       TShark fields to export"
    echo ""
    exit 1
}

# 1. Basic Argument Check
if [ -z "$1" ] || [[ "$1" == "--help" ]]; then usage; fi

URL=$1
shift 

# 2. Parse Options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --parallel) PARALLEL="$2"; shift ;;
        --duration) DURATION="$2"; shift ;;
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
if [[ ! "$URL" =~ ^https?:// ]]; then
    echo -e "${RED}Error:${NC} URL must start with http:// or https://"
    exit 1
fi

if [[ ! -f "main.py" ]]; then
    echo -e "${RED}Error:${NC} main.py not found in current directory."
    exit 1
fi

echo -e "${GREEN}Preparing Orchestration...${NC}"
echo -e "Target:   ${YELLOW}$URL${NC}"
echo -e "Parallel: ${YELLOW}$PARALLEL instance(s)${NC}"

# 4. Construct Command Array
CMD_ARGS=(
    python main.py
    "$URL"
    --vbox-path "$VBOX_PATH"
    --vm "$VM_NAME"
    --user "$USER"
    --password "$PASS"
    --snapshot "$SNAPSHOT"
    --venv "$VENV_PATH"
    --guest-script "$GUEST_SCRIPT"
    --base-host-path "$BASE_HOST_PATH"
    --parallel "$PARALLEL"
    --duration "$DURATION"
    --boot-timeout "$BOOT_TIMEOUT"
    --output "$GUEST_OUTPUT"
    --reg-path "$REG_PATH"
    --procmon-path "$PROCMON_PATH"
    --tshark-path "$TSHARK_PATH"
    --iface "$IFACE"
)

# Append TShark fields safely if they are defined
if [[ -n "$TSHARK_FIELDS" ]]; then
    CMD_ARGS+=(--tshark-fields $TSHARK_FIELDS)
fi

# 5. Execute
"${CMD_ARGS[@]}"

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}Orchestrator finished successfully.${NC}"
else
    echo -e "\n${RED}Orchestrator exited with an error.${NC}"
fi