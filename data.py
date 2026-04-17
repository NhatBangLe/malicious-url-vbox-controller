from dataclasses import dataclass
import datetime

from constants import DEFAULT_MS_HOST, DEFAULT_MS_LPORT, DEFAULT_MS_PAYLOAD, DEFAULT_MS_SRVPORT
from urls import DEFAULT_FETCH_MODE, DEFAULT_SOURCE

@dataclass
class CLIArguments:
    vbox_path: str
    vm: str
    user: str
    password: str
    snapshot: str
    script_path: str

    clean_up: bool = True
    execution_timeout: int = 300
    base_host_path: str = "./Audit_Results"
    source: str = DEFAULT_SOURCE
    api_key: str | None = None
    fetch_mode: str = DEFAULT_FETCH_MODE

    max_url: int | None = None
    duration: int = 30
    output: str = "Z:\\"
    boot_timeout: int = 300
    headless: bool = False

    reg_path: str | None = None
    procmon_path: str | None = None
    tshark_path: str | None = None
    tshark_fields: list[str] | None = None
    iface: int = 1

    ms_rpc_host: str = DEFAULT_MS_HOST
    ms_rpc_port: int = 55553
    ms_rpc_ssl: bool = True
    ms_rpc_uri: str | None = None
    ms_rpc_password: str | None = None
    ms_host: str = DEFAULT_MS_HOST
    ms_srvport: int = DEFAULT_MS_SRVPORT
    ms_lport: int = DEFAULT_MS_LPORT
    ms_payload: str = DEFAULT_MS_PAYLOAD
    ms_from_date: datetime.datetime | None = None
    ms_to_date: datetime.datetime | None = None

@dataclass
class ScriptArguments:
    script_path: str
    target_url: str
    signal_file: str = "AUDIT_COMPLETED"
    duration: int = 30
    output_path: str = "Z:\\"
    regview_path: str | None = None
    procmon_path: str | None = None
    tshark_path: str | None = None
    tshark_fields: list[str] | None = None
    interface_num: int = 1

@dataclass
class VBoxWorkflowConfiguration:
    """
Configuration for a single VirtualBox VM workflow.
    
Args:
    snapshot (str): The name of the snapshot to clone.
    base_host_path (str): The host directory where unique run folders will be created.
    script_args (ScriptArguments): The script arguments to run.
    boot_timeout (int): The maximum time (in seconds) to wait for the VM to boot.
    execution_timeout (int): The maximum time (in seconds) to wait for the guest script to complete.
    headless (bool): Whether to start the VM in headless mode. Defaults to False.
"""
    snapshot: str
    base_host_path: str
    script_args: ScriptArguments
    boot_timeout: int = 300
    execution_timeout: int = 60
    headless: bool = False
    clean_up: bool = True