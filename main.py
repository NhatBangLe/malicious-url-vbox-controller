import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import textwrap
from controllers.abuse_url_haus import (
    AbuseURLhausController,
    AbuseURLhausControllerOptions,
)
from data import ScriptArguments
from helpers import setup_logging
from controllers.vbox import VBoxController

SUPPORTED_SOURCES = {"ABUSE_HAUS": "abuse"}
DEFAULT_SOURCE = SUPPORTED_SOURCES["ABUSE_HAUS"]
SUPPORTED_FETCH_MODES = {"PAST_30DAYS": "past30", "ONLY_ACTIVE": "only_active"}
DEFAULT_FETCH_MODE = SUPPORTED_FETCH_MODES["PAST_30DAYS"]


def check_source(source: str):
    supported_sources = list(SUPPORTED_SOURCES.values())

    if source not in supported_sources:
        return DEFAULT_SOURCE
    return source


def check_fetch_mode(mode: str):
    supported_modes = list(SUPPORTED_FETCH_MODES.values())

    if mode not in supported_modes:
        return DEFAULT_FETCH_MODE
    return mode


def get_target_urls(source: str, api_key: str | None, mode: str):
    target_urls: list[str] = []

    if source == SUPPORTED_SOURCES["ABUSE_HAUS"]:
        if not api_key:
            raise
        options = AbuseURLhausControllerOptions(api_key=api_key)
        ctrl = AbuseURLhausController(options)

        if mode == SUPPORTED_FETCH_MODES["PAST_30DAYS"]:
            data = ctrl.get_past30_urls()
        elif mode == SUPPORTED_FETCH_MODES["ONLY_ACTIVE"]:
            data = ctrl.get_active_urls()
        else:
            data = ctrl.get_past30_urls()

        if data:
            with open("abuse_fetched_urls.json", "w") as f:
                ready_to_dump = list(map(lambda e: e.__dict__, data))
                json.dump(ready_to_dump, f, indent=2)
            target_urls = list(map(lambda e: e.url, data))

    return target_urls


def parse_args():
    parser = argparse.ArgumentParser(
        description="Host Orchestrator for VM System Audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=textwrap.dedent(
            """\n
            python main.py --vm "Win10_Base" --user "Admin" --password "Pass123" \\
                           --snapshot "Ready" --guest-script "C:\\audit.py" --duration 60
            """
        ),
    )

    # --- Infrastructure Arguments (Host side) ---
    parser.add_argument(
        "--vbox-path",
        default="VBoxManage",
        help="Path to VBoxManage executable (default: 'VBoxManage' from PATH)",
    )
    parser.add_argument("--vm", required=True, help="Base VM name")
    parser.add_argument("--user", required=True, help="Guest OS Admin username")
    parser.add_argument("--password", required=True, help="Guest OS password")
    parser.add_argument("--snapshot", required=True, help="Snapshot to clone")
    parser.add_argument(
        "--guest-script", required=True, help="Path to guest audit script"
    )
    parser.add_argument(
        "--execution-timeout",
        type=int,
        default=300,
        help="Max seconds to wait for guest script execution (default: 300)",
    )
    parser.add_argument(
        "--base-host-path",
        default="./Audit_Results",
        help="Host directory for results (default: ./Audit_Results)",
    )
    parser.add_argument(
        "--source",
        type=check_source,
        default=DEFAULT_SOURCE,
        help=f'Source for malicious URLs (default: "{DEFAULT_SOURCE}"). Supported: {list(SUPPORTED_SOURCES.values())}',
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="(Optional) API key for fetching malicious URLs from your source.",
    )
    parser.add_argument(
        "--fetch-mode",
        type=check_fetch_mode,
        default=DEFAULT_FETCH_MODE,
        help=f'Mode for fetching malicious URLs (default: "{DEFAULT_FETCH_MODE}"). Supported: {list(SUPPORTED_FETCH_MODES.values())}',
    )

    # --- Audit Arguments (Passed to Guest) ---
    parser.add_argument("--max-url", help="Maximum number of URLs to audit.")
    parser.add_argument(
        "--duration", type=int, default=30, help="Audit duration in seconds"
    )
    parser.add_argument(
        "--output",
        default="Z:\\",
        help="Guest-side output (Z: is usually the Shared Folder)",
    )
    parser.add_argument(
        "--boot-timeout",
        type=int,
        default=300,
        help="Seconds to wait for guest OS to boot (default: 300)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Start VMs in headless mode (no GUI)",
    )

    # --- Tool Path Overrides (Passed to Guest) ---
    parser.add_argument(
        "--reg-path", default=None, help="Path to RegistryChangesView.exe"
    )
    parser.add_argument("--procmon-path", default=None, help="Path to Procmon.exe")
    parser.add_argument("--tshark-path", default=None, help="Path to tshark.exe")
    parser.add_argument(
        "--iface", type=int, default=1, help="TShark Interface ID (default: 1)"
    )
    parser.add_argument(
        "--tshark-fields",
        nargs="*",
        default=None,
        help="Optional list of TShark fields to export (e.g., --tshark-fields frame.time ip.src ip.dst)",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    workflow_params = {
        "snapshot": args.snapshot,
        "base_host_path": args.base_host_path,
        "boot_timeout": args.boot_timeout,
        "execution_timeout": int(args.execution_timeout),
        "headless": bool(args.headless),
    }

    target_urls: list[str] = get_target_urls(
        source=args.source, api_key=args.api_key, mode=args.fetch_mode
    )
    if args.max_url:
        target_urls = target_urls[: int(args.max_url)]

    manager = VBoxController(
        user=args.user,
        password=args.password,
        base_vm_name=args.vm,
        vbox_path=args.vbox_path,
    )

    total_urls = len(target_urls)
    if total_urls == 0:
        logging.info(f"No URL to audit.")
        return

    logging.info(f"Launching audits for {total_urls} URL(s)...")
    with ThreadPoolExecutor(max_workers=total_urls) as executor:
        futures = [
            executor.submit(
                manager.run_workflow,
                **workflow_params,
                script_args=ScriptArguments(
                    script_path=str(args.guest_script),
                    target_url=target_url,
                    duration=int(args.duration),
                    output_path=str(args.output),
                    interface_num=int(args.iface),
                    tshark_path=str(args.tshark_path),
                    tshark_fields=args.tshark_fields,
                    procmon_path=str(args.procmon_path),
                    regview_path=str(args.reg_path),
                ),
            )
            for target_url in target_urls
        ]
        for future in futures:
            success, path = future.result()
            logging.info(
                f"Audit at {path} completed: {'SUCCESS' if success else 'FAILED'}"
            )


if __name__ == "__main__":
    setup_logging()
    main()
