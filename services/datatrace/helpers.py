from concurrent.futures import ThreadPoolExecutor
import logging
import mimetypes
from pathlib import Path


from data import ScriptArguments
from services.datatrace import DataTraceService
from services.datatrace.models import CreateTraceRequest, UploadTraceFileRequest


def upload_trace_files(
    service: DataTraceService,
    results_dir_path: str,
    vm_id: str,
    args: ScriptArguments,
    vul_error: str | None = None,
    description: str | None = None,
    risk_score: float | None = None,
):
    logging.info("Uploading trace files (vm_id: {vm_id})...")

    trace = CreateTraceRequest(
        target_url=args.target_url,
        vm_id=vm_id,
        vul_error=vul_error,
        duration=args.duration,
        description=description,
        risk_score=risk_score,
    )
    trace_id = service.create_trace(trace)

    dir_path = Path(results_dir_path)
    files: list[Path] = []
    for f in dir_path.iterdir():
        if f.is_file():
            files.append(f)
        else:
            for sub_file in f.iterdir():
                if sub_file.is_file():
                    files.append(sub_file)

    def read_and_upload(path: Path):
        content = path.read_bytes()
        filename = path.name

        data = UploadTraceFileRequest(
            trace_id=trace_id,
            content=content,
            filename=filename,
            mime_type=mimetypes.guess_type(filename)[0],
        )
        service.upload_trace_file(data)

    with ThreadPoolExecutor() as executor:
        # executor.map submits all files to the pool
        executor.map(read_and_upload, files)
