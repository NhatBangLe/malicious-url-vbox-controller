from abc import ABC, abstractmethod

from data import CLIArguments


class IScriptHandlingService(ABC):
    
    @abstractmethod
    def execute_script(self, args: CLIArguments) -> bool:
        """
        Execute a script with the given arguments.

        Args:
            args: Arguments for the script execution.

        Returns:
            bool: True if the script executed successfully, False otherwise.
        """
        pass