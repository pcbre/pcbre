import pkg_resources
import sysconfig


def find_so(name: str) -> str:
    # This terrible hack seems to be able to find the compiled acceleration library
    extension = sysconfig.get_config_var('EXT_SUFFIX')
    if extension is None:
        raise ValueError("No system extension for shared objects")

    return pkg_resources.resource_filename('pcbre.accel', name + extension)
