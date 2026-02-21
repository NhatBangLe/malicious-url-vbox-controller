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

    def __init__(self, user: str, password: str, base_vm_name: str = ""):
        """
        Initializes the VBoxManager with guest credentials and base VM info.

        Args:
            user (str): The administrator username for the guest OS.
            password (str): The password for the guest OS user.
            base_vm_name (str): The name of the source VM to clone from.
        """
        self.base_vm_name = base_vm_name
        self.user = user
        self.password = password

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
        cmd = ["VBoxManage"] + args
        result = subprocess.run(cmd, capture_output=capture, text=True)
        if result.returncode != 0:
            _logger.error(f"VBox Command Failed: {result.stderr.strip() if result.stderr else 'Unknown error'}")
            raise RuntimeError("VBoxManage command failed")
        return result

    def run_workflow(self, snapshot: str, base_host_path: str, venv_path: str, python_script: list[str]):
        """
        Orchestrates an independent VM run: clones from snapshot, mounts a unique 
        shared folder, executes a Python script in a venv, and destroys the instance.

        Args:
            snapshot (str): The name of the snapshot to clone.
            base_host_path (str): The host directory where unique run folders will be created.
            venv_path (str): The absolute path to the virtual environment folder inside the guest.
            python_script (list[str]): The script path and arguments to run (e.g., ["C:\\main.py", "--arg1"]).

        Returns:
            tuple: (bool, str) - A success flag and the absolute path to the host output directory.
        """
        # 1. Generate Unique ID for this specific run
        instance_id = f"Run_{uuid.uuid4().hex[:8]}"
        instance_vm_name = f"{self.base_vm_name}_{instance_id}"
        
        # Create a unique subfolder for this instance's results
        unique_host_path = os.path.abspath(os.path.join(base_host_path, instance_id))
        os.makedirs(unique_host_path, exist_ok=True)

        _logger.info(f"--- Launching Instance: {instance_vm_name} ---")
        _logger.info(f"--- Local Output Path: {unique_host_path} ---")

        try:
            # 2. Create Linked Clone
            self._call([
                "clonevm", self.base_vm_name, 
                "--snapshot", snapshot, 
                "--options", "link", 
                "--name", instance_vm_name, 
                "--register"
            ])

            # 3. Setup Shared Folder pointing to the UNIQUE subfolder
            self._call(["sharedfolder", "add", instance_vm_name, 
                        "--name", "VM_Exchange", 
                        "--hostpath", unique_host_path, 
                        "--automount"])

            # 4. Start VM
            self._call(["startvm", instance_vm_name, "--type", "headless"])

            # 5. Wait for Boot
            if not self._wait_for_boot(instance_vm_name):
                return False, unique_host_path

            # 6. Execute Python Script
            # Resolves the path to the python interpreter within the guest's venv
            venv_python = os.path.join(venv_path, "Scripts", "python.exe")
            exec_args = [
                "guestcontrol", instance_vm_name, "run",
                "--username", self.user, "--password", self.password,
                "--run-elevated", "--", venv_python
            ]
            
            result = self._call(exec_args + python_script)
            if result:
                _logger.info(f"Instance {instance_id} finished successfully.")
                return True, unique_host_path
            
            return False, unique_host_path
        except Exception as e:
            _logger.error(f"Error in instance {instance_id}: {e}")
            return False, unique_host_path
        finally:
            # 7. Cleanup: Ensures the VM is stopped and the linked clone is deleted
            _logger.info(f"Destroying instance {instance_vm_name}...")
            try:
                self._call(["controlvm", instance_vm_name, "poweroff"])
                time.sleep(3) # Ensure locks are released
                self._call(["unregistervm", instance_vm_name, "--delete"])
            except Exception as cleanup_err:
                _logger.warning(f"Cleanup failed for {instance_vm_name}: {cleanup_err}")

    def _wait_for_boot(self, vm_name: str, timeout: int = 300):
        """
        Polls the guest VM until Guest Additions are active and responding.

        Args:
            vm_name (str): The name of the VM instance to check.
            timeout (int): Max seconds to wait before failing. Defaults to 300.

        Returns:
            bool: True if the guest is ready, False if timeout is reached.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                check = self._call(["guestproperty", "get", vm_name, "/VirtualBox/GuestAdd/VBoxService/Version"])
                if check and "Value:" in check.stdout:
                    return True
            except RuntimeError:
                # Command might fail if the VM process is still initializing
                pass
            time.sleep(5)
        return False