import logging

from data import ScriptArguments, VBoxWorkflowConfiguration
from services import IScriptHandlingService
from services.datatrace import DataTraceService
from services.datatrace.helpers import upload_trace_files
from services.vbox import VirtualBoxService
from urls.helper import TargetURLHelper


class DefaultScriptHandlingService(IScriptHandlingService):

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def execute_script(self, args) -> bool:
        handler = TargetURLHelper.get_handler(source=args.source, api_key=args.api_key)
        target_urls: list[str] = handler.get_urls(mode=args.fetch_mode)

        total_urls = len(target_urls)
        if total_urls == 0:
            self._logger.info(f"No URL to audit.")
            return True
        self._logger.info(f"Found {total_urls} URL(s) to audit.")

        total_run = int(args.max_url) if args.max_url else total_urls
        self._logger.info(f"Launching {total_run} audits...")
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

        datatrace_service: DataTraceService | None = None
        if args.datatrace_endpoint:
            datatrace_service = DataTraceService(args.datatrace_endpoint)
        manager = VirtualBoxService(
            user=args.user,
            password=args.password,
            base_vm_name=args.vm,
            vbox_path=args.vbox_path,
        )
        for workflow_args in args_list:
            config = VBoxWorkflowConfiguration(
                snapshot=args.snapshot,
                base_host_path=args.base_host_path,
                boot_timeout=args.boot_timeout,
                execution_timeout=int(args.execution_timeout),
                headless=bool(args.headless),
                script_args=workflow_args,
            )

            result = manager.run_workflow(config=config)
            self._logger.info(
                f"Audit at {result.results_dir} completed: {'SUCCESS' if result.success else 'FAILED'}"
            )

            if datatrace_service:
                upload_trace_files(
                    service=datatrace_service,
                    args=workflow_args,
                    results_dir_path=result.results_dir,
                    vm_id=result.vm_id,
                    description=f"URL source: {args.source}",
                )

        self._logger.info(f"Launched {total_run} audit(s) for {total_urls} URL(s).")
        return True
