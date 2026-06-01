# Conform Sidekick installer (resolve-native)

End users download a platform ZIP from [GitHub Releases](https://github.com/beauwright/Conform-Sidekick/releases), extract it, and run:

| Platform | Action |
|----------|--------|
| **Windows** | Double-click `Install-ConformSidekick.bat` (or run `Install-ConformSidekick.ps1`) |
| **macOS / Linux** | `chmod +x install_conform_sidekick.sh && ./install_conform_sidekick.sh` |

That copies `Conform Sidekick.py`, `conform_sidekick/`, and `helpers/` into Resolve’s **Scripts → Utility** folder.

Developers can use junctions instead: `ResolveScript/link_to_resolve.ps1`.
