from dataclasses import dataclass
import logging
from typing import Literal

import requests


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
class AbuseURLhausControllerOptions:
    api_key: str
    base_url: str = "https://urlhaus-api.abuse.ch/files/exports"


class AbuseURLhausController:

    def __init__(self, options: AbuseURLhausControllerOptions) -> None:
        self._logger = logging.getLogger(__name__)
        self._options = options

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
