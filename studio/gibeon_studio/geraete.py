"""Kameras und Capture-Karten erkennen – mit besonderem Blick auf Elgato.

USB-Karten von Elgato (Cam Link, Cam Link 4K, HD60 S+, HD60 X, 4K60 S+, 4K S, 4K X, Neo) sind
UVC-Geräte und laufen mit dem Kernel-Treiber. Studio wählt für sie das beste unkomprimierte Format
(z. B. 1080p60 in NV12/YUYV) statt dem, was GStreamer zufällig nimmt.
Ältere Karten (Game Capture HD, HD60, HD60 S, HD60 Pro, 4K60 Pro) haben keinen Linux-Treiber;
die PCIe-Karten 4K60 Pro MK.2, 4K Pro und Cam Link Pro brauchen einen eigenen Treiber.
Studio erkennt solche Karten und sagt es, statt still nichts zu zeigen.
"""

from pathlib import Path

from . import v4l2modes

ELGATO_USB = "0fd9"
ELGATO_PCI = "0x1cfa"
# Elgato baut auch Stream Decks, Mikrofone und Lichter – nur Capture-Geräte zählen
CAPTURE_WORDS = ("capture", "cam link", "hd60", "4k60", "4k x", "4k s", "4k pro", "neo")
PCI_NAMES = {"0x000e": "Elgato 4K60 Pro MK.2", "0x0012": "Elgato 4K Pro", "0x0011": "Elgato Cam Link Pro"}

SYS = Path("/sys")


def _read(p):
    try:
        return Path(p).read_text().strip()
    except OSError:
        return ""


def _usb_device(path):
    """USB-Gerät (Ordner mit idVendor) über einem sysfs-Pfad."""
    p = Path(path).resolve()
    for d in [p, *p.parents]:
        if (d / "idVendor").exists():
            return d
    return None


def _pci_device(path):
    p = Path(path).resolve()
    for d in [p, *p.parents]:
        if (d / "vendor").exists() and (d / "class").exists():
            return d
    return None


def describe(node):
    """Zusatzwissen zu /sys/class/video4linux/videoN: {"elgato": bool, "capture": bool}."""
    dev = Path(node) / "device"
    name = _read(Path(node) / "name").lower()
    usb = _usb_device(dev)
    elgato = False
    if usb is not None:
        elgato = _read(usb / "idVendor") == ELGATO_USB
    else:
        pci = _pci_device(dev)
        elgato = pci is not None and _read(pci / "vendor") == ELGATO_PCI
    capture = elgato or any(w in name for w in CAPTURE_WORDS)
    return {"elgato": elgato, "capture": capture}


def capture_mode(device, fps_max=60):
    """Bestes Format einer Capture-Karte: 1080p mit höchster Bildrate (bis 60), unkomprimiert bevorzugt.
    None, wenn die Karte nichts meldet (dann entscheidet GStreamer)."""
    modes = v4l2modes.list_modes(device)
    return pick_capture_mode(modes, fps_max)


RAW_ORDER = {"NV12": 4, "YUYV": 3, "UYVY": 3, "YU12": 2, "MJPG": 1}


def pick_capture_mode(modes, fps_max=60):
    usable = [m for m in modes if m["format"] in RAW_ORDER and m["width"] <= 3840]
    if not usable:
        return None

    def score(m):
        full_hd = m["width"] == 1920 and m["height"] == 1080
        return (full_hd, min(m["fps"], fps_max), RAW_ORDER[m["format"]], m["width"] * m["height"])
    best = dict(max(usable, key=score))
    best["fps"] = min(best["fps"], fps_max)
    return best


def unsupported():
    """Angeschlossene Elgato-Capture-Karten ohne nutzbares Videogerät: [Text]."""
    out = []
    nodes = [Path(n).resolve() for n in (SYS / "class" / "video4linux").glob("video*")]

    def has_node(dev):
        return any(str(n).startswith(str(dev.resolve()) + "/") for n in nodes)

    for d in (SYS / "bus" / "usb" / "devices").glob("*"):
        if _read(d / "idVendor") != ELGATO_USB:
            continue
        product = _read(d / "product") or "Elgato-Gerät"
        if not any(w in product.lower() for w in CAPTURE_WORDS) or has_node(d):
            continue
        out.append(f"{product}: Für diese Karte gibt es keinen Linux-Treiber – sie funktioniert leider nur "
                   "unter Windows/macOS. Unterstützt werden Cam Link, HD60 S+, HD60 X, 4K60 S+, 4K S, 4K X und Neo.")
    for d in (SYS / "bus" / "pci" / "devices").glob("*"):
        if _read(d / "vendor") != ELGATO_PCI or has_node(d):
            continue
        name = PCI_NAMES.get(_read(d / "device"), "Elgato-PCIe-Karte")
        out.append(f"{name}: Die Karte ist eingebaut, aber Gibeon OS hat dafür noch keinen Treiber.")
    return out
