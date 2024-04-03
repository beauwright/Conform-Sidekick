# Conform Sidekick Developer Information

## Repo overview
  - **PythonInterface**: Contains the business logic, interfacing with DaVinci Resolve and handling photo conversions. This codebase operates as a sidecar application to the frontend. This file must be compiled using PyInstaller before compiling the Tauri app.
  - **TauriApp**: The frontend/user interface. A Tauri application developed using React and TypeScript. Uses the  PythonInterface code for all business logic.

## Requirements
- Node installed with version >= 18
- Rust installed
- Python installed with version >= 3.10
- The Tauri CLI installed
    ```
    npm install --save-dev @tauri-apps/cli

    ```
- Run npm install to get all dependencies

## Setup
- The Python sidecar must be compiled and properly named
    - In the PythonInteface folder, run
    ```
    pip install -r requirements.txt
    pyinstaller even_photos_resolve.py --onefile --name --name even_photos_resolve-[your platform identifier goes here]
    ```

    - The platform identifier for x64 windows is x86_64-pc-windows-msvc.exe
    - The platform identifier for ARM macOS is aarch64-apple-darwin
    - The platform identifier for Intel macOS is x86_64-apple-darwin
- DaVinci Resolve Studio is not required for compiling but is essential for testing/development.
    - This documentation is more useful than the official documentation for DaVinci Resolve's scripting API https://deric.github.io/DaVinciResolve-API-Docs/


For development builds, use this command:
```
npm run tauri dev
```

For release builds, use this command:
```
npm run tauri build
```

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
