import subprocess
import time
import os
import uuid
import logging

_logger = logging.getLogger(__name__)

class VBoxManager:
    """
    Manages VirtualBox VM lifecycles by creating independent linked clones,
    executing guest scripts with admin privileges, and cleaning up instances.
    """

    def __init__(self, user: str, password: str, base_vm_name: str = "", vbox_path: str = "VBoxManage"):
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

    def _call(self, args: list[str], capture=True):
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
        result = subprocess.run(cmd, capture_output=capture, text=True)
        if result.returncode != 0:
            if result.stderr:
                _logger.error(f"VBox Command Failed: {result.stderr.strip()}")
            elif result.stdout:
                _logger.error(f"VBox Command Failed: {result.stdout.strip()}")
            else:
                _logger.error("VBox Command Failed with no output.")
            raise RuntimeError("VBoxManage command failed")
        return result

    def run_workflow(self, snapshot: str, base_host_path: str, venv_path: str, python_script: list[str], boot_timeout: int = 300):
        """
        Orchestrates an independent VM run: clones from snapshot, mounts a unique 
        shared folder, executes a Python script in a venv, and destroys the instance.

        Args:
            snapshot (str): The name of the snapshot to clone.
            base_host_path (str): The host directory where unique run folders will be created.
            venv_path (str): The absolute path to the virtual environment folder inside the guest.
            python_script (list[str]): The script path and arguments to run (e.g., ["C:\\main.py", "--arg1"]).
            boot_timeout (int): The maximum time (in seconds) to wait for the VM to boot.

        Returns:
            tuple: (bool, str) - A success flag and the absolute path to the host output directory.
        """
        # 1. Initialization
        instance_id = f"Run_{uuid.uuid4().hex[:8]}"
        instance_vm_name = f"{self.base_vm_name}_{instance_id}"
        unique_host_path = os.path.abspath(os.path.join(base_host_path, instance_id))

        _logger.info(f"[{instance_id}] Starting workflow orchestration.")
        _logger.debug(f"[{instance_id}] Target Snapshot: {snapshot}")

        try:
            # 2. Directory Creation
            _logger.info(f"[{instance_id}] Creating host output directory: {unique_host_path}")
            os.makedirs(unique_host_path, exist_ok=True)
            
            # 3. Cloning
            _logger.info(f"[{instance_id}] Creating linked clone: {instance_vm_name}")
            self._call([
                "clonevm", self.base_vm_name, 
                "--snapshot", snapshot, 
                "--options", "link", 
                "--name", instance_vm_name, 
                "--register"
            ])

            # 4. Shared Folder Setup
            _logger.info(f"[{instance_id}] Attaching shared folder 'VM_Exchange' to {unique_host_path}")
            self._call(["sharedfolder", "add", instance_vm_name, 
                        "--name", "VM_Exchange", 
                        "--hostpath", unique_host_path, 
                        "--automount"])

            # 5. Power On
            _logger.info(f"[{instance_id}] Powering on VM (headless mode)")
            self._call(["startvm", instance_vm_name, "--type", "headless"])

            # 6. Boot Monitoring
            _logger.info(f"[{instance_id}] Waiting for Guest Additions (Timeout: {boot_timeout}s)")
            if not self._wait_for_boot(instance_vm_name, boot_timeout):
                _logger.error(f"[{instance_id}] CRITICAL: Boot timeout reached. Guest OS failed to respond.")
                return False, unique_host_path
            _logger.info(f"[{instance_id}] Guest OS is ready.")

            # --- ADD THIS BUFFER ---
            _logger.info(f"[{instance_id}] Guest detected. Stabilizing for 15s before execution...")
            time.sleep(15) 
            # -----------------------

           # 7. Script Execution
            venv_python = os.path.join(venv_path, "Scripts", "python.exe")
            _logger.info(f"[{instance_id}] Launching guest script: {python_script[0]}")
            exec_args = [
                "guestcontrol", instance_vm_name, "run",
                "--username", self.user, "--password", self.password,
                "--", venv_python
            ]
            
            # Combine core args with the script + script arguments
            self._call(exec_args + python_script)
            _logger.info(f"[{instance_id}] Guest script execution completed successfully.")
            return True, unique_host_path
        except Exception as e:
            _logger.error(f"Error in instance {instance_id}: {e}")
            return False, unique_host_path
        finally:
            # 8. Teardown
            _logger.info(f"[{instance_id}] Initiating cleanup and VM destruction.")
            try:
                # We use a broader check to ensure we try to delete even if poweroff fails
                _logger.debug(f"[{instance_id}] Sending poweroff signal...")
                self._call(["controlvm", instance_vm_name, "poweroff"])
                
                # Give VirtualBox a moment to release file locks
                time.sleep(3) 
                
                _logger.debug(f"[{instance_id}] Unregistering and deleting VM files...")
                self._call(["unregistervm", instance_vm_name, "--delete"])
                _logger.info(f"[{instance_id}] Cleanup complete. Instance destroyed.")
            except Exception as cleanup_err:
                _logger.warning(f"[{instance_id}] Cleanup encountered an error: {cleanup_err}")

    def _wait_for_boot(self, vm_name: str, timeout: int):
        start_time = time.time()
        # List of properties that indicate Guest Additions are alive
        check_properties = [
            "/VirtualBox/GuestAdd/VBoxService/Version",
            "/VirtualBox/GuestAdd/VBoxGuestAttr/Runtime/OS/Name",
            "/VirtualBox/GuestAdd/Components/VBoxService.exe"
        ]

        while time.time() - start_time < timeout:
            for prop in check_properties:
                result = self._call(["guestproperty", "get", vm_name, prop])
                if result.stdout and "Value:" in result.stdout:
                    val = result.stdout.split("Value:")[1].strip()
                    if val:
                        _logger.info(f"[{vm_name}] Detected guest activity via {prop}")
                        return True
            time.sleep(5)
        return False