# Nuke Viewer Clipboard

Copy the current Viewer input to the clipboard at its output resolution in **Rec.709** with **Ctrl+Alt+C**, then paste it into an application that accepts images.

[한국어](README.ko.md) · [Download](https://github.com/tardis7732/nuke-viewer-clipboard/releases/latest)

## Features

- Uses the active Viewer’s primary input and current frame.
- Follows the connected node’s output format, including Reformat dimensions.
- Copies the full frame regardless of Viewer zoom or pan, without interface margins or overlays.
- Converts the working RGB space to linear Rec.709, then applies Nuke's `rec709` output curve once.
- Applies Viewer gain, gamma and saturation once, including controls handled by an Input Process.
- Places an opaque, 8-bit RGB image on the clipboard, with a Rec.709 ICC profile in the PNG data.
- Renders one frame to a temporary PNG and removes the temporary directory after loading it.

For example, a **1920 × 1080 Reformat** connected to the Viewer produces a **1920 × 1080 clipboard image**. Black bars that are part of the image remain intact.

## Installation

Tested on **Windows with Nuke 17.1v1**. Uses Nuke’s bundled Python and Qt; no additional packages are required. Other operating systems and Nuke versions have not been tested.

1. Download and extract the latest release.
2. Copy the `NukeViewerClipboard` folder into your `.nuke` directory. On Windows, enter `%USERPROFILE%\.nuke` in File Explorer’s address bar.
3. Add this line to `.nuke/init.py`. Create the file if it does not exist; keep any existing contents.

   ```python
   import nuke
   nuke.pluginAddPath("./NukeViewerClipboard")
   ```

4. Restart Nuke.

The plugin’s `menu.py` stays inside `NukeViewerClipboard`; do not replace your existing `.nuke/menu.py`.

## Usage

1. Display the desired node in the Viewer and stop on a frame.
2. Press **Ctrl+Alt+C**, or choose **Viewer → Copy Frame to Clipboard**.
3. Wait for the single-frame render to finish, then use **Ctrl+V** in the destination application.

A tooltip shows the copied frame number and image dimensions. Render time depends on the upstream node graph. Cancelling the render leaves the existing clipboard contents unchanged.

Output is fixed to Rec.709. The selected Viewer Process/display LUT is not baked in. A Viewer set to Raw, sRGB, Display P3, ACES tone mapping or Rec.1886 can therefore look different. Viewer gain and gamma adjustments are included; reset them to 1 for an unadjusted export.

### Change the shortcut

Edit `NukeViewerClipboard/menu.py` and pass the key combination you prefer:

```python
import copy_viewer_frame

copy_viewer_frame.register(shortcut="Ctrl+Alt+C")
```

Use a combination that is free in your Nuke setup, then restart Nuke. To update the binding in a running session, run the same two lines in Nuke’s Script Editor.

## Output behavior

The plugin evaluates the connected graph at full resolution, temporarily disabling proxy mode. It creates a temporary render branch, then restores the selection, frame, proxy setting and script modification flag, without adding an undo step.

The temporary PNG is created inside the operating system’s temporary directory, under `nuke_viewer_clipboard_*`. The plugin removes that directory after reading the image, including when rendering fails or is cancelled. Nothing is written alongside the source footage or saved into the project. A forced process termination can leave temporary files behind.

## Scope

- The output is an 8-bit display-referred preview. Alpha transparency and floating-point HDR values are not retained.
- Viewer A/B wipes, comparison modes, 3D views, masks and overlays are not reproduced. The primary input is copied.
- RGB and individual R/G/B/A/Y channel display modes are supported. Other channel display modes are rejected.
- Single-input Input Process nodes and Groups can be copied; external dependencies or relative expressions inside custom processes may require a dedicated export setup. The IP before/after setting is relative to the Rec.709 output transform.
- OCIO projects require a linear Rec.709 space in the config. Nuke's default config and the bundled ACES CG 1.3/2.0 configs are supported; an unrecognized config produces an error.
- The PNG representation carries a Rec.709 profile. Applications that use an untagged clipboard bitmap or paste into an existing document may use the destination document's profile instead.

## Uninstall

Remove the `pluginAddPath` line from `.nuke/init.py`, delete the `NukeViewerClipboard` folder, and restart Nuke.

## License

[MIT](LICENSE)
