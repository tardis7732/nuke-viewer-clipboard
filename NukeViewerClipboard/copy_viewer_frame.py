"""Copy the active Viewer's look at full resolution, encoded as sRGB."""

import os
import tempfile

import nuke

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets


MENU_PATH = "Viewer/Copy Frame to Clipboard"
SHORTCUT = "Ctrl+Alt+C"
__version__ = "1.0.0"
_busy = False


def _value(node, name, default=None):
    knob = node.knob(name)
    return knob.value() if knob is not None else default


def _clone_process(original):
    """Copy the Viewer Process without touching its live instance."""
    if original.Class() not in ("ViewerLUT", "OCIODisplay"):
        raise RuntimeError("This custom Viewer Process needs a dedicated export setup.")
    clone = getattr(nuke.nodes, original.Class())()
    excluded = {
        "name", "xpos", "ypos", "selected", "onCreate", "onDestroy",
        "knobChanged", "updateUI", "autolabel", "rootNodeUpdated", "panel",
    }
    # Set the display before the dependent view enumeration.
    keys = list(original.knobs())
    keys = [k for k in ("colorspace", "display", "view") if k in keys] + [
        k for k in keys if k not in ("colorspace", "display", "view")
    ]
    for name in keys:
        knob = clone.knob(name)
        if knob is None or name in excluded:
            continue
        if original[name].Class() in ("Tab_Knob", "Text_Knob", "PyScript_Knob", "Script_Knob"):
            continue
        knob.fromScript(original[name].toScript(False))
    return clone


def _to_srgb(source, process):
    """Convert already displayed RGB, without undoing or repeating its view transform."""
    encoding = "sRGB"  # Native Raw/None has no encoding; use an sRGB display.
    if process is not None and process.Class() == "OCIODisplay":
        import PyOpenColorIO as ocio
        from ocionuke.config import getOCIOConfig

        if _value(process, "invert", False) or _value(process, "disable", False):
            raise RuntimeError("Use an enabled, forward Viewer Process before copying.")
        config = getOCIOConfig()
        display = process["display"].value()
        view = process["view"].value()
        name = config.getDisplayViewColorSpaceName(display, view)
        if name == "<USE_DISPLAY_NAME>":
            name = display
        space = config.getColorSpace(name)
        if space is not None and space.isData():
            # Raw skips the view transform. Interpret its visible RGB in the
            # selected display encoding, rather than as scene-linear pixels.
            space = config.getColorSpace(display)
            if space is None and _value(nuke.root(), "OCIO_config") == "nuke-default":
                space = config.getColorSpace("sRGB")
        if space is None:
            raise RuntimeError("Cannot determine this Viewer's display encoding.")
        if space.getReferenceSpaceType() == ocio.REFERENCE_SPACE_DISPLAY:
            if space.getEncoding() == "hdr-video":
                # The clipboard is an SDR screen preview. Keep the HDR Viewer's
                # rendered RGB appearance on an sRGB display; decoding PQ/HLG
                # to absolute luminance here would brighten and clip that preview.
                # This is not a luminance-preserving HDR-to-SDR master conversion.
                return source
            target = config.getColorSpace("srgb_display")
            if target is None:
                target = config.getColorSpace("sRGB - Display")
            if target is None or target.getReferenceSpaceType() != ocio.REFERENCE_SPACE_DISPLAY:
                raise RuntimeError("The config needs an sRGB display colorspace.")
            conversion = nuke.nodes.OCIOColorSpace(inputs=[source])
            conversion["in_colorspace"].setValue(space.getName())
            conversion["out_colorspace"].setValue(target.getName())
            return conversion
        elif _value(nuke.root(), "OCIO_config") == "nuke-default":
            encoding = space.getName()
        else:
            raise RuntimeError("This config needs display-referred colorspaces for look-preserving export.")
    elif process is not None:
        if process.Class() != "ViewerLUT":
            raise RuntimeError("This custom Viewer Process needs a dedicated export setup.")
        encoding = _value(process, "current", "sRGB")

    encoding = {"linear": "sRGB", "raw": "sRGB", "Gamma1.8": "1.80", "Gamma2.2": "2.20",
                "Gamma2.4": "2.40", "Gamma2.6": "2.60"}.get(encoding, encoding)
    if encoding not in ("sRGB", "rec709", "1.80", "2.20", "2.40", "2.60", "BT1886"):
        raise RuntimeError("Unsupported Viewer display encoding: {}".format(encoding))
    if encoding == "sRGB":
        return source
    # Decode only the display transfer curve and encode sRGB. The Viewer
    # Process (including ACES tone mapping) has already been baked upstream.
    return nuke.nodes.Colorspace(
        inputs=[source], channels="rgb", colorspace_in=encoding, colorspace_out="sRGB",
    )


def _srgb_profile():
    """Describe sRGB samples for PNG-aware, color-managed applications."""
    profile = QtGui.QColorSpace(QtGui.QColorSpace.NamedColorSpace.SRgb)
    if not profile.isValid():
        raise RuntimeError("Could not create the sRGB image profile.")
    return profile


def _save_input_process(node, path):
    """Serialize an actual DAG input-process node, including Group contents."""
    with node.parent():
        selected = nuke.selectedNodes()
        try:
            for item in selected:
                item.setSelected(False)
            node.setSelected(True)
            nuke.nodeCopy(path)
        finally:
            node.setSelected(False)
            for item in selected:
                item.setSelected(True)


def _render_frame(viewer, source, frame, view, process, path):
    """Render one sRGB frame and restore the working script."""
    parent = viewer.parent()
    ip_name = _value(viewer, "input_process_node", "")
    ip_enabled = _value(viewer, "input_process", False)
    with parent:
        ip = nuke.toNode(ip_name) if ip_enabled and ip_name else None
        selected = nuke.selectedNodes()
    controls = {
        name: float(_value(viewer, name, 1))
        for name in ("gain", "gamma", "saturation")
    }
    # Nuke delegates matching controls to IP first, then Viewer Process.
    owners = {
        name: next((node for node in (ip, process)
                    if node is not None and node.knob(name) is not None), None)
        for name in controls
    }

    def bind_controls(clone, original):
        for name, value in controls.items():
            if owners[name] is original:
                knob = clone[name]
                knob.clearAnimated()
                knob.setValue(value)

    root = nuke.root()
    was_modified = root.modified()
    was_proxy = root.proxy()
    previous_frame = nuke.frame()
    undo_disabled = nuke.Undo.disabled()
    sandbox = None
    try:
        if not undo_disabled:
            nuke.Undo.disable()
        root.setProxy(False)
        if nuke.frame() != frame:
            nuke.frame(frame)
        ip_path = os.path.join(os.path.dirname(path), "input_process.nk")
        if ip is not None:
            _save_input_process(ip, ip_path)
        with parent:
            sandbox = nuke.nodes.Group(name="_ClipboardFrame", inputs=[source])
        with sandbox:
            current = nuke.nodes.Input()
            layer = _value(viewer, "channels", "rgba")
            if layer not in ("rgba", "rgb"):
                current = nuke.nodes.Shuffle(inputs=[current], **{"in": layer})
            gain = controls["gain"]
            if gain != 1 and owners["gain"] is None:
                current = nuke.nodes.Multiply(inputs=[current], channels="rgb", value=gain)
            ip_before = (
                _value(viewer, "viewerInputOrder", "before viewer process")
                == "before viewer process"
            )
            if ip is not None and ip_before:
                clone = nuke.nodePaste(ip_path)
                bind_controls(clone, ip)
                clone.setInput(0, current)
                current = clone
            if process is not None:
                clone = _clone_process(process)
                bind_controls(clone, process)
                clone.setInput(0, current)
                current = clone
            if ip is not None and not ip_before:
                clone = nuke.nodePaste(ip_path)
                bind_controls(clone, ip)
                clone.setInput(0, current)
                current = clone
            gamma = controls["gamma"]
            if gamma != 1 and owners["gamma"] is None:
                current = nuke.nodes.Gamma(inputs=[current], channels="rgb", value=gamma)
            saturation = controls["saturation"]
            if saturation != 1 and owners["saturation"] is None:
                current = nuke.nodes.Saturation(inputs=[current], saturation=saturation)
            style = _value(viewer, "layer_display_style", "RGB")
            channel = {
                "R": "r", "G": "g", "B": "b", "A": "a",
                "Red": "r", "Green": "g", "Blue": "b", "Alpha": "a",
            }.get(style)
            process_handles_channels = process is not None and process.knob("channel_selector") is not None
            if channel and not process_handles_channels:
                current = nuke.nodes.Expression(
                    inputs=[current], expr0=channel, expr1=channel, expr2=channel,
                )
            elif style in ("Y", "Luminance") and not process_handles_channels:
                luminance = "0.2126*r+0.7152*g+0.0722*b"
                current = nuke.nodes.Expression(
                    inputs=[current], expr0=luminance, expr1=luminance, expr2=luminance,
                )
            elif style not in ("RGB", "Y", "Luminance") and channel is None:
                raise RuntimeError(
                    "Switch the Viewer channel display to RGB, R, G, B, A or Y before copying."
                )
            current = _to_srgb(current, process)
            # Crop only the format boundary, never detect black pixels in the image.
            fmt = current.format()
            width, height = fmt.width(), fmt.height()
            current = nuke.nodes.Crop(inputs=[current], reformat=False)
            current["box"].setValue((0, 0, width, height))
            writer = nuke.nodes.Write(
                inputs=[current], file=path.replace("\\", "/"),
                file_type="png", channels="rgb",
            )
            # sRGB is already encoded above: do not apply a second transform.
            writer["raw"].setValue(True)
            writer["datatype"].setValue("8 bit")
            nuke.execute(writer, frame, frame, views=[view])
        return {
            "viewer": viewer.fullName(), "source": source.fullName(),
            "frame": frame, "width": width, "height": height,
            "colorspace": "sRGB",
            "viewer_process": _value(viewer, "viewerProcess", "None"),
        }
    finally:
        # Restore global state even if removing a temporary node fails.
        try:
            if sandbox is not None:
                nuke.delete(sandbox)
        finally:
            try:
                with parent:
                    for item in nuke.selectedNodes():
                        item.setSelected(False)
                    for item in selected:
                        item.setSelected(True)
            finally:
                try:
                    root.setProxy(was_proxy)
                    if nuke.frame() != previous_frame:
                        nuke.frame(previous_frame)
                finally:
                    try:
                        root.setModified(was_modified)
                    finally:
                        if not undo_disabled:
                            nuke.Undo.enable()


def copy_frame():
    """Copy one full-format sRGB frame to the clipboard."""
    global _busy
    if _busy:
        return None
    _busy = True
    try:
        window = nuke.activeViewer()
        if window is None:
            raise RuntimeError("Open a Viewer and display a frame first.")
        viewer = window.node()
        active = window.activeInput()
        source = viewer.input(active) if active is not None and active >= 0 else None
        if source is None:
            raise RuntimeError("Connect an image to the active Viewer input first.")
        frame = int(_value(viewer, "frame", nuke.frame()))
        view = window.view()
        process = nuke.ViewerProcess.node(viewer=viewer.fullName())
        app = QtWidgets.QApplication.instance()
        if app is None:
            raise RuntimeError("Copy Frame requires the Nuke GUI.")

        with tempfile.TemporaryDirectory(prefix="nuke_viewer_clipboard_") as temp:
            path = os.path.join(temp, "frame.png")
            result = _render_frame(viewer, source, frame, view, process, path)
            picture = QtGui.QImage(path)
            if picture.isNull():
                raise RuntimeError("The frame render returned no image.")
            picture = picture.convertToFormat(QtGui.QImage.Format_RGB32)
            picture.setColorSpace(_srgb_profile())
            if (picture.width(), picture.height()) != (result["width"], result["height"]):
                raise RuntimeError("The rendered image size did not match the input format.")

        png = QtCore.QByteArray()
        buffer = QtCore.QBuffer(png)
        buffer.open(QtCore.QIODevice.WriteOnly)
        if not picture.save(buffer, "PNG"):
            raise RuntimeError("Could not prepare the clipboard image.")
        buffer.close()
        data = QtCore.QMimeData()
        data.setImageData(picture)
        data.setData("image/png", png)
        app.clipboard().setMimeData(data)
        message = "Copied sRGB frame {frame:g} ({width} x {height})".format(**result)
        nuke.tprint(message)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), message)
        return result
    except Exception as exc:
        nuke.message("Copy Frame to Clipboard\n\n{}".format(exc))
        return None
    finally:
        _busy = False


def register(shortcut=SHORTCUT):
    """Install once, including when reloaded in a running session."""
    if not nuke.GUI:
        return
    menu = nuke.menu("Nuke")
    if menu.findItem(MENU_PATH) is not None:
        menu.removeItem(MENU_PATH)
    menu.addCommand(MENU_PATH, copy_frame, shortcut, shortcutContext=0)
