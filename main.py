import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
import textwrap
from data import ScriptArguments
from helpers import setup_logging
from vbox_manager import VBoxManager


def validate_url(url: str):
    """Basic validation to ensure the URL is well-formed before starting VMs."""
    if not url.startswith(("http://", "https://")):
        raise argparse.ArgumentTypeError(
            f"Invalid URL '{url}'. Must start with http:// or https://"
        )
    return url


def parse_args():
    parser = argparse.ArgumentParser(
        description="Host Orchestrator for VM System Audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=textwrap.dedent(
            """\n
            # Single audit run:
            python main.py --vm "Win10_Base" --user "Admin" --password "Pass123" \\
                           --snapshot "Ready" --venv "C:\\venv" --guest-script "C:\\audit.py" \\
                           "https://example.com" --duration 60

            # Parallel audit (3 instances at once):
            python main.py --vm "Win10_Base" --user "Admin" --password "Pass123" \\
                           --snapshot "Ready" --venv "C:\\venv" --guest-script "C:\\audit.py" \\
                           "https://suspicious.site" --parallel 3 --tshark-fields ip.src ip.dst
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
    parser.add_argument("--parallel", type=int, default=1, help="Number of instances")
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

    # --- Audit Arguments (Passed to Guest) ---
    parser.add_argument(
        "url", type=validate_url, help="The URL to browse (must start with http/https)"
    )
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

    manager = VBoxManager(
        user=args.user,
        password=args.password,
        base_vm_name=args.vm,
        vbox_path=args.vbox_path,
    )

    script_args = ScriptArguments(
        script_path=str(args.guest_script),
        target_url=str(args.url),
        duration=int(args.duration),
        output_path=str(args.output),
        interface_num=int(args.iface),
        tshark_path=str(args.tshark_path),
        tshark_fields=args.tshark_fields,
        procmon_path=str(args.procmon_path),
        regview_path=str(args.reg_path),
    )

    workflow_params = {
        "snapshot": args.snapshot,
        "base_host_path": args.base_host_path,
        "script_args": script_args,
        "boot_timeout": args.boot_timeout,
        "execution_timeout": int(args.execution_timeout),
        "headless": bool(args.headless),
    }

    if args.parallel > 1:
        logging.info(f"Launching {args.parallel} parallel audits...")
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = [
                executor.submit(manager.run_workflow, **workflow_params)
                for _ in range(args.parallel)
            ]
            for future in futures:
                success, path = future.result()
                logging.info(
                    f"Audit at {path} completed: {'SUCCESS' if success else 'FAILED'}"
                )
    else:
        success, path = manager.run_workflow(**workflow_params)
        logging.info(f"Audit finished. Host results in: {path}")


if __name__ == "__main__":
    setup_logging()
    main()
