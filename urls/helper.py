from urls import DEFAULT_FETCH_MODE, DEFAULT_SOURCE, ITargetURLHandler, TargetURLFetchMode, TargetURLSource
from urls.abuse_url_haus import AbuseURLhausHandler, AbuseURLhausHandlerOptions


class TargetURLHelper:

    @staticmethod
    def get_handler(source: str, api_key: str | None = None) -> ITargetURLHandler:
        """
        Factory method to get the appropriate URL handler based on source and mode.
            
        Args:
            source (str): The source of the URLs.
            api_key (str, optional): The API key for the source. Defaults to None.

        Returns:
            ITargetURLHandler: The handler for the specified source and mode.
        
        Raises:
            ValueError: If the source or mode is not supported or if an API key is required for certain sources.
        """
        reliableSrc = TargetURLHelper.check_source(source)

        match reliableSrc:
            case "ABUSE_HAUS":
                if not api_key:
                    raise ValueError("API key is required for ABUSE_HAUS source")
                options = AbuseURLhausHandlerOptions(api_key=api_key)
                handler = AbuseURLhausHandler(options)
            case _:
                raise ValueError(f"Unsupported source: {source}")
        return handler

    @staticmethod
    def check_source(source: str) -> TargetURLSource:
        """
        Validates and converts the source string to TargetURLSource.
        
        Args:
            source (str): The source of the URLs.

        Returns:
            TargetURLSource: The validated source.
        """
        match source:
            case "ABUSE_HAUS" | "abuse_haus":
                return "ABUSE_HAUS"
            case _:
                return DEFAULT_SOURCE

    @staticmethod
    def check_fetch_mode(mode: str) -> TargetURLFetchMode:
        """
        Validates and converts the fetch mode string to TargetURLFetchMode.
        
        Args:
            mode (str): The mode to fetch URLs.

        Returns:
            TargetURLFetchMode: The validated fetch mode.

        Raises:
            ValueError: If the mode is not supported.
        """
        match mode:
            case "PAST_30DAYS" | "past_30days":
                return "PAST_30DAYS"
            case "ONLY_ACTIVE" | "only_active":
                return "ONLY_ACTIVE"
            case _:
                return DEFAULT_FETCH_MODE