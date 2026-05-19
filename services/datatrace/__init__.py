from dataclasses import asdict

import requests

from services.datatrace.models import CreateTraceRequest, UploadTraceFileRequest


class DataTraceService:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def create_trace(self, data: CreateTraceRequest):
        """
        Creates a new trace and returns its ID.
        """
        response = requests.post(url=f"{self.endpoint}/trace/create", json=asdict(data))
        response.raise_for_status()

        return str(response.json())

    def upload_trace_file(self, data: UploadTraceFileRequest):
        """
        Uploads a new trace file along with its metadata.
        Returns the S3 key of the uploaded file.
        """
        files = {
            "file": (
                (data.filename, data.content, data.mime_type)
                if data.mime_type
                else (data.filename, data.content)
            )
        }
        response = requests.post(
            url=f"{self.endpoint}/trace/{data.trace_id}/upload", files=files
        )
        response.raise_for_status()

        return str(response.json())
