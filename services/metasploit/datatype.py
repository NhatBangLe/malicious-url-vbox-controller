
from dataclasses import dataclass
from typing import Dict


@dataclass
class MetasploitClientOptions:
    password: str | None = None
    host: str = "127.0.0.1"
    port: int = 55553
    ssl: bool = False
    uri: str | None = None


@dataclass
class MetasploitSearchResult(Dict):
    type: str
    name: str
    fullname: str
    rank: str
    disclosuredate: str


@dataclass
class MaliciousWebServerMetadata:
    job_id: str
    url: str
    host: str
    port: int
    uri_path: str
    payload: str