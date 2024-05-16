"""
This file serves to return a DaVinci Resolve object
"""
import sys
import importlib.machinery
import importlib.util
import os

def load_dynamic(module_name, file_path):
    module = None
    spec = None
    loader = importlib.machinery.ExtensionFileLoader(module_name, file_path)
    if loader:
        spec = importlib.util.spec_from_loader(module_name, loader)
    if spec:
        module = importlib.util.module_from_spec(spec)
    if module:
        loader.exec_module(module)
    return module
    
def GetResolve():
    try:
        if sys.platform.startswith("darwin"):
            sys.path.append("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/")
            import fusionscript as bmd
            return bmd.scriptapp("Resolve")
        elif sys.platform.startswith("win"):
            fusion_script_path = os.getenv("RESOLVE_SCRIPT_LIB")
            if fusion_script_path:
                script_module = load_dynamic("fusionscript", fusion_script_path)
            else:
                script_module = load_dynamic("fusionscript", "C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\fusionscript.dll")
            return script_module.scriptapp("Resolve")
        else:
            raise ResolveConnectionFailed("Unsupported platform", 20)
    except ImportError:
        raise ResolveConnectionFailed("Could not connect to Resolve", 10)

class ResolveConnectionFailed(Exception):
    pass