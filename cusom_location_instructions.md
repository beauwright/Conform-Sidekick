These instructions are intended to help users who have not installed DaVinci Resolve Studio in the standard location help Conform Sidekick connect to DaVinci Resolve. Users who install DaVinci Resolve Studio normally should not need to follow these instructions as Conform Sidekick automatically looks for DaVinci Resolve in its default installation location.

### For macOS Users:

1. **Open Terminal**: Find the Terminal application and open it.
2. **Edit `.bash_profile` or `.zshrc` File**: Depending on the shell you are using, you will need to edit either your `~/.bash_profile` (for Bash) or `~/.zshrc` (for Zsh, which is the default shell in macOS Catalina and later). You can open this file with a text editor like nano, by typing `nano ~/.bash_profile` or `nano ~/.zshrc` in the Terminal.
3. **Add Python Path**: In the opened file, add the following line at the end:
   ```
   export PYTHONPATH="[Absolute path to your DaVinci Resolve.app]/Contents/Libraries/Fusion/:$PYTHONPATH"
   ```
   This line adds the directory where the DaVinci Resolve libraries are located to the Python path.
4. **Save and Close**: Save the changes and close the editor. If you're using nano, you can do this by pressing `Ctrl + O`, `Enter`, and then `Ctrl + X`.
5. **Apply Changes**: For the changes to take effect, either close and reopen your Terminal or source the profile file by typing `source ~/.bash_profile` or `source ~/.zshrc`.

### For Windows Users:

1. **Open System Properties**: Right-click on ‘This PC’ or ‘My Computer’ on the desktop or in File Explorer, then click ‘Properties’. Click ‘Advanced system settings’ on the left sidebar.
2. **Environment Variables**: In the System Properties window, go to the ‘Advanced’ tab and click on ‘Environment Variables’.
3. **Add New Variable**: Under ‘System variables’, click on ‘New’ to create a new variable. 
    - In the ‘Variable name’ field, enter `RESOLVE_SCRIPT_LIB`.
    - In the ‘Variable value’ field, enter the path to the `fusionscript.dll` file inside of DaVinci Resolve. The default location of this file is `C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\fusionscript.dll` but you'll need to specify the full path to the `fusionscript.dll` file in the custom installation location.
4. **Click OK**: After adding the variable, click ‘OK’ on all open windows to apply the changes.
5. **Restart**: You may need to restart any command prompts or applications that will use this environment variable for the changes to take effect.

### General Instructions:

- If you encounter any issues, verify that the paths you've added are correct and accessible.
- This setup requires a basic understanding of editing system environment variables and paths. Be cautious when making changes to system settings.