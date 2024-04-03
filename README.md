# Conform Sidekick

## Download

Find the latest version to download on the [releases page](https://github.com/beauwright/Conform-Sidekick/releases/latest)

## Key Features

- **Fix Odd Resolution Media**: Automatically detect media with odd numbers its resolutions that can cause failed renders when rendering at source resolution with codecs such as ProRes that do not support odd resolutions. Conform Sidekick fixes these images by stretching them by 1px to make them even resolutions. Conform Sidekick creates a new file with the adjusted image and automatically updates your DaVinci Resolve project to reference this new file. Original files remain untouched and unchanged.

- **Find Interlaced Video Quickly**: Get the timecode of every interlaced video used in your current timeline.

- **Find Compound Clips Quickly**: Get the timecode of every compound clip in your project.

## Compatibility and Use

### Compatibility
- **DaVinci Resolve Studio**: Conform Sidekick uses scripting features only found in DaVinci Resolve Studio, and is not compatible with the free version of DaVinci Resolve.
    - Ensure external scripting is set to either local or network in Preferences/General or Conform Sidekick will fail to connect to Resolve.

### Limitations
- **Media Conversion**: Currently, Conform Sidekick can identify odd resolutions in image sequences and video files but can only automatically adjust and replace image files.
- The macOS build supports a non-default location for DaVinci Resolve's location as long the path to the folder containing fusionscript.so is added to PATH. The Windows build does not currently support non-standard installation locations. (Users that install DaVinci Resolve Studio normally do not need to worry about this, everything should work automatically.)

### Usage

Conform Sidekick is licensed under the [GNU GPLv3 license.](https://www.gnu.org/licenses/gpl-3.0.en.html) This is a summary of GPLv3's key implications; it is not a substitute for reviewing the full license terms which can be found at: https://www.gnu.org/licenses/gpl-3.0.en.html
- **Commercial Use:** You are permitted to use Conform Sidekick for commercial projects.
- **Modification and Redistribution:** You must release any modifications and derivative works of the Conform Sidekick application under the same GPLv3 license, which means that all released improved versions of Conform Sidekick must also be free open source software. 
    - This does not cause problems for any commercial film or TV productions using the Conform Sidekick application and refers to modified versions of the code of the program itself.
- **No Warranty:** Conform Sidekick is provided 'as is', without any warranty. Please review [the full GNU GPLv3 license](https://www.gnu.org/licenses/gpl-3.0.en.html) for all terms and conditions.

## Community and Support

### Feedback and Contributions
- **Feature Suggestions and Bug Reporting**: Please suggest features through the Discussions page and report bugs with the Issues pages.

### Contributing
- **Open to Contributions**: Contributions are welcome! Reach out in the Discussions page if you are interested in contributing.
  - **Development Setup Guide**: A guide for setting up a development environment can be found [here](/TauriApp/README.md).

### Disclaimer
- **Independent Development**: Conform Sidekick is independently developed and is not affiliated with Blackmagic Design or DaVinci Resolve.
