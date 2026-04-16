import argparse
import textwrap
from data import CLIArguments
from services.default import DefaultScriptHandlingService
from urls import DEFAULT_FETCH_MODE, DEFAULT_SOURCE
from helpers import setup_logging


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
        "--clean-up",
        action="store_true",
        default=True,
        help="Clean up VM and snapshots after execution (default: True)",
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
    parser.add_argument("--max-url", default=None, help="Maximum number of URLs to audit.")
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

    raw_args = parser.parse_args()
    args = CLIArguments(
        vbox_path=raw_args.vbox_path,
        vm=raw_args.vm,
        user=raw_args.user,
        password=raw_args.password,
        snapshot=raw_args.snapshot,
        script_path=raw_args.script_path,

        clean_up=raw_args.clean_up,
        execution_timeout=raw_args.execution_timeout,
        base_host_path=raw_args.base_host_path,
        source=raw_args.source,
        api_key=raw_args.api_key,
        fetch_mode=raw_args.fetch_mode,

        max_url=raw_args.max_url,
        duration=raw_args.duration,
        output=raw_args.output,
        boot_timeout=raw_args.boot_timeout,
        headless=raw_args.headless,

        reg_path=raw_args.reg_path,
        procmon_path=raw_args.procmon_path,
        tshark_path=raw_args.tshark_path,
        tshark_fields=raw_args.tshark_fields,
        iface=raw_args.iface,
    )

    return args


def main():
    args = parse_args()

    handler = DefaultScriptHandlingService()
    handler.execute_script(args)

if __name__ == "__main__":
    setup_logging()
    main()
