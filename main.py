import argparse
import logging
import textwrap
from urls import DEFAULT_FETCH_MODE, DEFAULT_SOURCE
from data import ScriptArguments
from helpers import setup_logging
from services.vbox import VirtualBoxService
from urls.helper import TargetURLHelper


def parse_args():
    parser = argparse.ArgumentParser(
        description="Host Orchestrator for VM System Audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=textwrap.dedent(
            """\n
            python main.py --vm "Win10_Base" --user "Admin" --password "Pass123" \\
                           --snapshot "Ready" --script-path "C:\\audit.py" --duration 60
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
        "--script-path",
        required=True,
        help="Path to the directory containing the script in the guest",
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
        type=str,
        default=DEFAULT_SOURCE,
        help=f'Source for malicious URLs (default: "{DEFAULT_SOURCE}"), case insensitive. Supported: ABUSE_HAUS',
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="(Optional) API key for fetching malicious URLs from your source.",
    )
    parser.add_argument(
        "--fetch-mode",
        type=str,
        default=DEFAULT_FETCH_MODE,
        help=f'Mode for fetching malicious URLs (default: "{DEFAULT_FETCH_MODE}"), case insensitive. Supported: PAST_30DAYS, ONLY_ACTIVE',
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

    handler = TargetURLHelper.get_handler(source=args.source, api_key=args.api_key)
    target_urls: list[str] = handler.get_urls(mode=args.fetch_mode)

    manager = VirtualBoxService(
        user=args.user,
        password=args.password,
        base_vm_name=args.vm,
        vbox_path=args.vbox_path,
    )

    total_urls = len(target_urls)
    if total_urls == 0:
        logging.info(f"No URL to audit.")
        return
    logging.info(f"Found {total_urls} URL(s) to audit.")

    total_run = int(args.max_url) if args.max_url else total_urls
    logging.info(f"Launching {total_run} audits...")
    args_list = [
        ScriptArguments(
            script_path=str(args.script_path),
            target_url=target_url,
            duration=int(args.duration),
            output_path=str(args.output),
            interface_num=int(args.iface),
            tshark_fields=args.tshark_fields,
            tshark_path=args.tshark_path,
            procmon_path=args.procmon_path,
            regview_path=args.reg_path,
        )
        for target_url in target_urls[:total_run]
    ]
    for workflow_args in args_list:
        success, path = manager.run_workflow(
            **workflow_params, script_args=workflow_args
        )
        logging.info(f"Audit at {path} completed: {'SUCCESS' if success else 'FAILED'}")

    logging.info(f"Launched {total_run} audit(s) for {total_urls} URL(s).")


if __name__ == "__main__":
    setup_logging()
    main()
