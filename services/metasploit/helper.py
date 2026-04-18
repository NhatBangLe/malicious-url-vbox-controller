from pymetasploit3.msfrpc import MsfRpcClient

from services.metasploit.datatype import MetasploitClientOptions


class MetasploitHelper:

    @staticmethod
    def create_client(options: MetasploitClientOptions):
        password = options.password if options.password is not None else ""
        uri = options.uri if options.uri is not None else "/api/"
        return MsfRpcClient(password=password, 
                            server=options.host, 
                            port=options.port, 
                            ssl=options.ssl,
                            uri=uri)
    
    @staticmethod
    def get_module_type(fullname: str):
        """
        Get the module type and path from the full module name.
        Args:
            fullname: The full module name, e.g. "exploit/windows/browser/ms17_010_eternalblue".
        Returns:
            The module type and path, e.g. ("exploit", "windows/browser/ms17_010_eternalblue").
        """
        module_type, module_path = fullname.split('/', 1)
        return module_type, module_path