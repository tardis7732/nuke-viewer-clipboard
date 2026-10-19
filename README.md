# Nuke Viewer Clipboard

Copy the current Viewer frame to the clipboard at its output resolution, **preserving the Viewer look and encoding the result as Rec.709**. Press **Ctrl+Alt+C**, then paste into an application that accepts images.

[한국어](README.ko.md) · [Download](https://github.com/tardis7732/nuke-viewer-clipboard/releases/latest)

## Features

- Uses the active Viewer’s primary input and current frame.
- Follows the connected node’s output format, including Reformat dimensions.
- Copies the full frame regardless of Viewer zoom or pan, without interface margins or overlays.
- Bakes the selected Viewer Process, including its view transform and tone mapping, before converting the display RGB to Rec.709.
- Applies Viewer gain, gamma and saturation once, respecting controls handled by the Input Process or Viewer Process.
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

The color pipeline is **Viewer Process and adjustments → display-color conversion → Rec.709 clipboard image**. The final conversion changes the display encoding while retaining the selected Viewer look. It does not remove ACES tone mapping or apply another view transform. Output uses Rec.709 primaries and Nuke's `rec709` transfer curve, described by the embedded ICC profile.

Raw bypasses the view transform, so its visible RGB is interpreted in the selected OCIO display's encoding. Native Raw/None and Nuke's default Raw view use an sRGB display assumption.

HDR Viewer displays can also be copied as an **SDR screen preview**. The selected HDR view transform and Viewer adjustments remain baked in; their rendered RGB values are interpreted as an sRGB screen preview and encoded as Rec.709. This preserves that preview without adding a tone map. It does not reproduce HDR-monitor luminance or create an HDR-to-SDR delivery master.

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
- Single-input Input Process nodes and Groups can be copied; external dependencies or relative expressions inside custom processes may require a dedicated export setup. IP ordering remains relative to the Viewer Process; Rec.709 conversion follows both.
- Supports native sRGB, Rec.709 and gamma display LUTs, standard SDR views in Nuke's default OCIO config, and the bundled ACES CG 1.3/2.0 displays. SDR ACES conversion requires display-referred source and Rec.1886 Rec.709 destination spaces; HDR displays use the screen-preview behavior above. Unsupported/custom Viewer Processes produce an error.
- Colors outside Rec.709's gamut and the 8-bit output range may clip. The plugin does not inspect the monitor's calibration or operating-system display profile.
- The PNG representation carries a Rec.709 profile. Applications that use an untagged clipboard bitmap or paste into an existing document may use the destination document's profile instead.

## Uninstall

Remove the `pluginAddPath` line from `.nuke/init.py`, delete the `NukeViewerClipboard` folder, and restart Nuke.

## License

[MIT](LICENSE)
