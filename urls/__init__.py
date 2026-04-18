from abc import ABC, abstractmethod
from typing import Literal


TargetURLSource = Literal["ABUSE_HAUS", "FILE"]
TargetURLFetchMode = Literal["PAST_30DAYS", "ONLY_ACTIVE"]

class ITargetURLHandler(ABC):
    
    @abstractmethod
    def get_urls(self, fetch_mode: TargetURLFetchMode | None = None,**kwargs) -> list[str]:
        """Fetches target URLs based on the specific source."""
        pass
