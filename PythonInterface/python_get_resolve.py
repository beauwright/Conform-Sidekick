#!/usr/bin/env python

"""
This file serves to return a DaVinci Resolve object
"""
import sys
import os
import sys

def load_dynamic(module_name, file_path):
    import importlib.machinery
    import importlib.util

    module = None
    spec = None
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
        
def GetResolve():
    script_module = None
    try:
        import fusionscript as script_module
    except ImportError:
        # Look for installer based environment variables:
        lib_path = os.getenv("RESOLVE_SCRIPT_LIB")
        if lib_path:
            try:
                script_module = load_dynamic("fusionscript", lib_path)
            except ImportError:
                pass
        if not script_module:
            # Look for default install locations:
            path = ""
            ext = ".so"
            if sys.platform.startswith("darwin"):
                path = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/"
            elif sys.platform.startswith("win") or sys.platform.startswith("cygwin"):
                ext = ".dll"
                path = "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\"
            elif sys.platform.startswith("linux"):
                path = "/opt/resolve/libs/Fusion/"

            script_module = load_dynamic("fusionscript", path + "fusionscript" + ext)

    try:
        return script_module.scriptapp("Resolve")
    except:
        raise ImportError("Could not locate module dependencies")
    

class ResolveConnectionFailed(Exception):
    pass