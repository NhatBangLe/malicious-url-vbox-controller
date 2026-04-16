import subprocess
import time
import os
import uuid
import logging
import json

from data import ScriptArguments, VBoxWorkflowConfiguration

class VirtualBoxService:
    """
    Manages VirtualBox VM lifecycles by creating independent linked clones,
    executing guest scripts with admin privileges, and cleaning up instances.
    """

    def __init__(
        self,
        user: str,
        password: str,
        base_vm_name: str = "",
        vbox_path: str = "VBoxManage",
    ):
        """
        Initializes the VBoxManager with guest credentials and base VM info.

        Args:
            user (str): The administrator username for the guest OS.
            password (str): The password for the guest OS user.
            base_vm_name (str): The name of the source VM to clone from.
            vbox_path (str): Path to the VBoxManage executable. Defaults to "VBoxManage".
        """
        self.base_vm_name = base_vm_name
        self.user = user
        self.password = password
        self.vbox_path = vbox_path
        self._logger = logging.getLogger(__name__)

    def _call(
        self,
        args: list[str],
        capture: bool = True,
        except_error_codes: list[int] | None = None,
    ):
        """
        Executes a VBoxManage command as a subprocess.

        Args:
            args (list[str]): List of arguments to append to 'VBoxManage'.
            capture (bool): Whether to capture stdout and stderr. Defaults to True.

        Returns:
            subprocess.CompletedProcess: The result of the command execution.

        Raises:
            RuntimeError: If the VBoxManage command returns a non-zero exit code.
        """
        cmd = [self.vbox_path] + args
        self._logger.debug(f"Executing: {' '.join(cmd)}")

        try:
            # subprocess.run is synchronous; it WILL wait for VBoxManage.exe to exit.
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                errors="replace",  # Handles potential encoding issues from the guest
            )

            if result.returncode != 0 and (
                except_error_codes is None
                or result.returncode not in except_error_codes
            ):
                # Get the cleanest error message possible
                err_msg = (
                    result.stderr or result.stdout or "No output message"
                ).strip()
                raise RuntimeError(f"Exit code {result.returncode}. {err_msg}")

            return result

        except FileNotFoundError:
            self._logger.critical(f"VBoxManage not found at: {self.vbox_path}")
            raise RuntimeError("VirtualBox is not installed or path is incorrect.")

    def run_workflow(self, config: VBoxWorkflowConfiguration) -> tuple[bool, str]:
        """
        Orchestrates an independent VM run: clones from snapshot, mounts a unique
        shared folder, executes a Python script in a venv, and destroys the instance.

        Args:
            config (VBoxWorkflowConfiguration): The configuration for the workflow.

        Returns:
            tuple: (bool, str) - A success flag and the absolute path to the host output directory.
        """
        # 1. Initialization
        instance_id = f"Run_{uuid.uuid4().hex[:8]}"
        instance_vm_name = f"{self.base_vm_name}_{instance_id}"
        unique_host_path = os.path.abspath(os.path.join(config.base_host_path, instance_id))

        self._logger.info(f"[{instance_id}] Starting workflow...")
        self._logger.debug(f"[{instance_id}] Target Snapshot: {config.snapshot}")

        try:
            # 2. Directory Creation
            self._logger.info(
                f"[{instance_id}] Creating host output directory: {unique_host_path}"
            )
            os.makedirs(unique_host_path, exist_ok=True)

            # 3. Cloning
            self._logger.info(f"[{instance_id}] Creating linked clone: {instance_vm_name}")
            self._call(
                [
                    "clonevm",
                    self.base_vm_name,
                    "--snapshot",
                    config.snapshot,
                    "--options",
                    "link",
                    "--name",
                    instance_vm_name,
                    "--register",
                ]
            )

            # 4. Shared Folder Setup
            self._logger.info(
                f"[{instance_id}] Attaching shared folder 'VM_Exchange' to {unique_host_path}"
            )
            self._call(
                [
                    "sharedfolder",
                    "add",
                    instance_vm_name,
                    "--name",
                    "VM_Exchange",
                    "--hostpath",
                    unique_host_path,
                    "--automount",
                ]
            )

            # 5. Power On
            self._logger.info(f"[{instance_id}] Powering on VM")
            self._call(
                [
                    "startvm",
                    instance_vm_name,
                    "--type",
                    "headless" if config.headless else "gui",
                ]
            )

            # 6. Boot Monitoring
            self._logger.info(
                f"[{instance_id}] Waiting for Guest Additions (Timeout: {config.boot_timeout}s)"
            )
            if not self._wait_for_boot(instance_vm_name, config.boot_timeout):
                self._logger.error(
                    f"[{instance_id}] CRITICAL: Boot timeout reached. Guest OS failed to respond."
                )
                return False, unique_host_path
            self._logger.info(f"[{instance_id}] Guest OS is ready.")
            self._logger.info(
                f"[{instance_id}] Guest detected. Stabilizing for 10s before execution..."
            )
            time.sleep(10)

            # 7. Write a config file in guest
            self._logger.info(f"[{instance_id}] Building guest config...")

            # Write a config file
            config_filename = "config.json"
            host_config_path = os.path.join(unique_host_path, config_filename)
            guest_config_path = os.path.join(config.script_args.script_path, config_filename)
            with open(host_config_path, "w", encoding="utf-8") as f:
                json.dump(
                    config.script_args.__dict__,
                    f,
                    indent=2,
                )
            self._logger.info(
                f"[{instance_id}] Deploying {config_filename} to guest {guest_config_path}..."
            )
            self._call(
                [
                    "guestcontrol",
                    instance_vm_name,
                    "copyto",
                    host_config_path,
                    guest_config_path,
                    "--username",
                    self.user,
                    "--password",
                    self.password,
                ]
            )

            time.sleep(2)

            # 8. POLLING: Check whether the guest script has signaled completion by creating a file in the shared folder
            self._logger.info(f"[{instance_id}] Waiting for completion signal...")

            start_poll = time.time()
            success = False
            host_signal_path = os.path.join(unique_host_path, config.script_args.signal_file)

            while (time.time() - start_poll) < config.execution_timeout:
                if os.path.exists(host_signal_path):
                    self._logger.info(
                        f"[{instance_id}] Signal detected. Execution completed."
                    )
                    success = True
                    time.sleep(
                        5
                    )  # Wait before cleanup to ensure all file operations are finished on the guest side
                    break
                time.sleep(2)  # Frequency of folder check

            if not success:
                self._logger.warning(
                    f"[{instance_id}] Timed out after {config.execution_timeout}s."
                )
            elif os.path.exists(host_signal_path):
                # Cleanup signal on Host
                try:
                    os.remove(host_signal_path)
                except:
                    pass

            self._logger.info(f"[{instance_id}] Guest script finished successfully.")
            return success, unique_host_path
        except Exception as e:
            self._logger.error(f"Error in instance {instance_id}: {e}")
            return False, unique_host_path
        finally:
            if config.clean_up:
                self._cleanup_vm(instance_vm_name)

    def _cleanup_vm(self, vm_name: str):
        self._logger.info(f"[{vm_name}] Initiating cleanup and VM destruction.")
        try:
            # We use a broader check to ensure we try to delete even if poweroff fails
            self._logger.debug(f"[{vm_name}] Sending poweroff signal...")
            self._call(["controlvm", vm_name, "poweroff"])

            # Give VirtualBox a moment to release file locks
            time.sleep(3)

            self._logger.debug(f"[{vm_name}] Unregistering and deleting VM files...")
            self._call(["unregistervm", vm_name, "--delete"])
            self._logger.info(f"[{vm_name}] Cleanup complete. Instance destroyed.")
        except Exception as cleanup_err:
            self._logger.warning(f"[{vm_name}] Cleanup encountered an error: {cleanup_err}")

    def _wait_for_boot(self, vm_name: str, timeout: int):
        start_time = time.time()
        self._logger.info(f"[{vm_name}] Waiting for full OS initialization (User Shell)...")

        while time.time() - start_time < timeout:
            try:
                # This property specifically tracks active user sessions
                result = self._call(
                    [
                        "guestproperty",
                        "get",
                        vm_name,
                        "/VirtualBox/GuestInfo/OS/LoggedInUsersList",
                    ]
                )

                if "Value:" in result.stdout:
                    # If it's not empty, someone is logged in and the desktop is ready
                    val = result.stdout.split("Value:")[1].strip()
                    if val:
                        self._logger.info(
                            f"[{vm_name}] Shell detected. User(s) logged in: {val}"
                        )
                        # Add a 10s "settle" time for the desktop to finish loading icons/startup apps
                        time.sleep(10)
                        return True
            except Exception:
                pass

            time.sleep(5)
            self._logger.debug(
                f"[{vm_name}] OS still loading... ({int(time.time() - start_time)}s)"
            )

        return False
