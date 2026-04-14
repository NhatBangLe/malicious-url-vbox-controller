from dataclasses import dataclass
import json
import logging
from typing import Literal

import requests

from urls import ITargetURLHandler


@dataclass
class AbuseMaliciousURL:
    dateadded: str
    url: str
    url_status: Literal["online", "offline"]
    last_online: str
    threat: str
    tags: list[str]
    urlhaus_link: str
    reporter: str


@dataclass
class AbuseURLhausHandlerOptions:
    api_key: str
    base_url: str = "https://urlhaus-api.abuse.ch/files/exports"


class AbuseURLhausHandler(ITargetURLHandler):

    def __init__(self, options: AbuseURLhausHandlerOptions) -> None:
        self._logger = logging.getLogger(__name__)
        self._options = options

    def get_urls(self, fetch_mode=None, **kwargs) -> list[str]:
        if fetch_mode is None:
            fetch_mode = "past30"

        match fetch_mode:
            case "past30":
                urls = self.get_past30_urls()
            case "only_active":
                urls = self.get_active_urls()
            case _:
                self._logger.error(f"Unsupported fetch mode: {fetch_mode}")
                raise ValueError()

        if urls is None:
            raise ValueError("Failed to fetch URLs")
        
        if kwargs.get("dump_raw_data", False):
            with open("abuse_fetched_urls.json", "w") as f:
                ready_to_dump = list(map(lambda e: e.__dict__, urls))
                json.dump(ready_to_dump, f, indent=2)

        return list(map(lambda e: e.url, urls))

    def get_past30_urls(self) -> list[AbuseMaliciousURL] | None:
        url = f"{self._options.base_url}/recent.json?auth-key={self._options.api_key}"

        try:
            response = requests.get(url)
            response.raise_for_status()

            rawData: dict[str, list[dict]] = response.json()
            data = list(map(lambda e: AbuseMaliciousURL(**e[0]), rawData.values()))

            return data
        except Exception as err:
            self._logger.error(f"HTTP error occurred: {err}")

    def get_active_urls(self):
        url = f"{self._options.base_url}/online.json?auth-key={self._options.api_key}"

        try:
            response = requests.get(url)
            response.raise_for_status()

            rawData: dict[str, list[dict]] = response.json()
            data = list(map(lambda e: AbuseMaliciousURL(**e[0]), rawData.values()))

            return data
        except Exception as err:
            self._logger.error(f"HTTP error occurred: {err}")

