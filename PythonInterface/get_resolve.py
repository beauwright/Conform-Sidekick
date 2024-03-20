"""
This file serves to return a DaVinci Resolve object
"""
import sys
        
def GetResolve():
    try:
        if sys.platform.startswith("darwin"):
            sys.path.append("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/")
        elif sys.platform.startswith("win") or sys.platform.startswith("cygwin"):
            sys.path.append("C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\")
        elif sys.platform.startswith("linux"):
            sys.path.append("/opt/resolve/libs/Fusion/")
        import fusionscript as bmd
        return bmd.scriptapp("Resolve")
    except ImportError:
        raise ResolveConnectionFailed("Could not connect to Resolve", 10)

class ResolveConnectionFailed(Exception):
    pass