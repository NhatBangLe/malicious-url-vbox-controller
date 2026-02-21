import argparse
import logging
import sys
import os
from concurrent.futures import ThreadPoolExecutor
import textwrap
from vbox_manager import VBoxManager
from datetime import datetime

def setup_logging():
    logging_dir = "./logs"
    os.makedirs(logging_dir, exist_ok=True)
    
    # Create a unique filename based on the current start time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logging_dir, f"audit_{timestamp}.log")
    
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture everything at the root level

    # Clear existing handlers if main is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. File Handler: Detailed logs (DEBUG level) for the specific run
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    file_handler.setFormatter(file_formatter)

    # 2. Stream Handler: Cleaner console output (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info(f"Logging initialized. Full log: {log_file}")

def validate_url(url: str):
    """Basic validation to ensure the URL is well-formed before starting VMs."""
    if not url.startswith(("http://", "https://")):
        raise argparse.ArgumentTypeError(f"Invalid URL '{url}'. Must start with http:// or https://")
    return url

def parse_args():
    parser = argparse.ArgumentParser(
        description="Host Orchestrator for VM System Audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=textwrap.dedent('''\n
            # Single audit run:
            python main.py --vm "Win10_Base" --user "Admin" --password "Pass123" \\
                           --snapshot "Ready" --venv "C:\\venv" --guest-script "C:\\audit.py" \\
                           "https://example.com" --duration 60

            # Parallel audit (3 instances at once):
            python main.py --vm "Win10_Base" --user "Admin" --password "Pass123" \\
                           --snapshot "Ready" --venv "C:\\venv" --guest-script "C:\\audit.py" \\
                           "https://suspicious.site" --parallel 3 --tshark-fields ip.src ip.dst
            ''')
    )
    
    # --- Infrastructure Arguments (Host side) ---
    parser.add_argument("--vbox-path", default="VBoxManage", 
                        help="Path to VBoxManage executable (default: 'VBoxManage' from PATH)")
    parser.add_argument("--vm", required=True, help="Base VM name")
    parser.add_argument("--user", required=True, help="Guest OS Admin username")
    parser.add_argument("--password", required=True, help="Guest OS password")
    parser.add_argument("--snapshot", required=True, help="Snapshot to clone")
    parser.add_argument("--venv", required=True, help="Path to guest venv")
    parser.add_argument("--guest-script", required=True, help="Path to guest audit script")
    parser.add_argument("--parallel", type=int, default=1, help="Number of instances")
    parser.add_argument("--base-host-path", default="./Audit_Results", 
                        help="Host directory for results (default: ./Audit_Results)")

    # --- Audit Arguments (Passed to Guest) ---
    parser.add_argument("url", type=validate_url, help="The URL to browse (must start with http/https)")
    parser.add_argument("--duration", type=int, default=30, help="Audit duration in seconds")
    parser.add_argument("--output", default="Z:\\", help="Guest-side output (Z: is usually the Shared Folder)")
    parser.add_argument("--boot-timeout", type=int, default=300, 
                        help="Seconds to wait for guest OS to boot (default: 300)")

    # --- Tool Path Overrides (Passed to Guest) ---
    parser.add_argument("--reg-path", default="C:\\tools\\RegistryChangesView.exe",
                        help="Path to RegistryChangesView.exe")
    parser.add_argument("--procmon-path", default="C:\\tools\\Procmon.exe",
                        help="Path to Procmon.exe")
    parser.add_argument("--tshark-path", default="C:\\Program Files\\Wireshark\\tshark.exe",
                        help="Path to tshark.exe")
    parser.add_argument("--iface", type=int, default=1, help="TShark Interface ID (default: 1)")
    parser.add_argument("--tshark-fields", nargs='*', default=None,  
                        help="Optional list of TShark fields to export (e.g., --tshark-fields frame.time ip.src ip.dst)")

    return parser.parse_args()

def main():
    setup_logging()
    args = parse_args()

    manager = VBoxManager(
        user=args.user,
        password=args.password,
        base_vm_name=args.vm,
        vbox_path=args.vbox_path
    )

    # Reconstruct the arguments to be sent to the guest script
    # We skip host-specific args and keep the audit-specific ones
    python_script_args = [args.guest_script, args.url]
    python_script_args += ["--duration", str(args.duration)]
    python_script_args += ["--output", args.output]
    python_script_args += ["--reg-path", args.reg_path]
    python_script_args += ["--procmon-path", args.procmon_path]
    python_script_args += ["--tshark-path", args.tshark_path]
    python_script_args += ["--iface", str(args.iface)]
    
    if args.tshark_fields:
        python_script_args += ["--tshark-fields"] + args.tshark_fields

    workflow_params = {
        "snapshot": args.snapshot,
        "base_host_path": args.base_host_path,
        "venv_path": args.venv,
        "python_script": python_script_args,
        "boot_timeout": args.boot_timeout
    }

    if args.parallel > 1:
        logging.info(f"Launching {args.parallel} parallel audits...")
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = [executor.submit(manager.run_workflow, **workflow_params) for _ in range(args.parallel)]
            for future in futures:
                success, path = future.result()
                logging.info(f"Audit at {path} completed: {'SUCCESS' if success else 'FAILED'}")
    else:
        success, path = manager.run_workflow(**workflow_params)
        logging.info(f"Audit finished. Host results in: {path}")

if __name__ == "__main__":
    main()