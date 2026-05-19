from dataclasses import dataclass


@dataclass
class CreateTraceRequest:
    target_url: str
    vm_id: str
    duration: int | None = None
    vul_error: str | None = None
    description: str | None = None
    risk_score: float | None = None


@dataclass
class UploadTraceFileRequest:
    trace_id: str
    content: bytes
    filename: str
    mime_type: str | None = None
