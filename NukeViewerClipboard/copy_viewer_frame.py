"""Copy the active Viewer input at full resolution in Rec.709."""

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


def _to_rec709(source):
    """Convert working RGB primaries, then apply Nuke's rec709 curve once."""
    if _value(nuke.root(), "colorManagement", "Nuke") == "OCIO":
        conversion = nuke.nodes.OCIOColorSpace(inputs=[source])
        available = {name.split("\t", 1)[0]
                     for name in conversion["out_colorspace"].values()}
        candidates = ("Linear Rec.709 (sRGB)", "Utility - Linear - sRGB",
                      "Utility - Linear - Rec.709", "lin_rec709")
        target = next((name for name in candidates if name in available), None)
        if target is None and _value(nuke.root(), "OCIO_config") == "nuke-default":
            target = "linear"
        if target is None:
            raise RuntimeError("The OCIO config needs a linear Rec.709 colorspace.")
        conversion["in_colorspace"].setValue(nuke.root()["workingSpaceLUT"].value())
        conversion["out_colorspace"].setValue(target)
        source = conversion
    return nuke.nodes.ViewerLUT(inputs=[source], current="rec709", rgb_only=True)


def _rec709_profile():
    """Describe Rec.709 RGB samples for PNG-aware, color-managed applications."""
    curve = []
    for i in range(4096):
        encoded = i / 4095.0
        linear = (encoded / 4.5 if encoded < 0.081
                  else ((encoded + 0.099) / 1.099) ** (1 / 0.45))
        curve.append(round(linear * 65535))
    profile = QtGui.QColorSpace(QtGui.QColorSpace.Primaries.SRgb, curve)
    profile.setDescription("Rec.709")
    if not profile.isValid():
        raise RuntimeError("Could not create the Rec.709 image profile.")
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


def _render_frame(viewer, source, frame, view, path):
    """Render one Rec.709 frame and restore the working script."""
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
    # An Input Process can own a control; otherwise apply it externally once.
    owners = {
        name: ip if ip is not None and ip.knob(name) is not None else None
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
            current = _to_rec709(current)
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
            if channel:
                current = nuke.nodes.Expression(
                    inputs=[current], expr0=channel, expr1=channel, expr2=channel,
                )
            elif style in ("Y", "Luminance"):
                luminance = "0.2126*r+0.7152*g+0.0722*b"
                current = nuke.nodes.Expression(
                    inputs=[current], expr0=luminance, expr1=luminance, expr2=luminance,
                )
            elif style != "RGB":
                raise RuntimeError(
                    "Switch the Viewer channel display to RGB, R, G, B, A or Y before copying."
                )
            # Crop only the format boundary, never detect black pixels in the image.
            fmt = current.format()
            width, height = fmt.width(), fmt.height()
            current = nuke.nodes.Crop(inputs=[current], reformat=False)
            current["box"].setValue((0, 0, width, height))
            writer = nuke.nodes.Write(
                inputs=[current], file=path.replace("\\", "/"),
                file_type="png", channels="rgb",
            )
            # Rec.709 is already encoded above: do not apply a second transform.
            writer["raw"].setValue(True)
            writer["datatype"].setValue("8 bit")
            nuke.execute(writer, frame, frame, views=[view])
        return {
            "viewer": viewer.fullName(), "source": source.fullName(),
            "frame": frame, "width": width, "height": height,
            "colorspace": "Rec.709",
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
    """Copy one full-format Rec.709 frame to the clipboard."""
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
        app = QtWidgets.QApplication.instance()
        if app is None:
            raise RuntimeError("Copy Frame requires the Nuke GUI.")

        with tempfile.TemporaryDirectory(prefix="nuke_viewer_clipboard_") as temp:
            path = os.path.join(temp, "frame.png")
            result = _render_frame(viewer, source, frame, view, path)
            picture = QtGui.QImage(path)
            if picture.isNull():
                raise RuntimeError("The frame render returned no image.")
            picture = picture.convertToFormat(QtGui.QImage.Format_RGB32)
            picture.setColorSpace(_rec709_profile())
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
        message = "Copied Rec.709 frame {frame:g} ({width} x {height})".format(**result)
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
