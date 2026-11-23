"""Associate video and audio by physical device (USB stick or PCIe card), never by generic names.

Works for any capture card that brings its own sound device – Elgato, AVerMedia (Live Gamer
Mini/Portable …), Cam Link, no-name HDMI sticks: video and audio sit on the same USB
device (or, for PCIe cards, on the same PCI slot). The names shown are the card's own."""
import json
import re
import subprocess
from pathlib import Path


def usb_parent(path):
    try:
        resolved = Path(path).resolve(strict=True)
        for parent in (resolved, *resolved.parents):
            if (parent / 'idVendor').is_file() and (parent / 'idProduct').is_file():
                return str(parent)
    except (OSError, RuntimeError):
        pass
    return ''


_PCI = re.compile(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]')


def pci_parent(path):
    """PCIe-Karten (z. B. Elgato 4K60 Pro, Live Gamer 4K): Steckplatz ohne Funktionsnummer –
    Bild und Ton liegen dort oft auf verschiedenen Funktionen desselben Steckplatzes."""
    try:
        resolved = Path(path).resolve(strict=True)
        for parent in (resolved, *resolved.parents):
            if _PCI.fullmatch(parent.name) and (parent / 'vendor').is_file():
                return 'pci:' + parent.name.rsplit('.', 1)[0]
    except (OSError, RuntimeError):
        pass
    return ''


def device_key(path):
    return usb_parent(path) or pci_parent(path)


def video_usb(device):
    name = Path(device).name
    if not re.fullmatch(r'video\d+', name):
        return ''
    return device_key(Path('/sys/class/video4linux') / name / 'device')


def source_usb(properties):
    card = str(properties.get('alsa.card', properties.get('api.alsa.card', '')))
    if card.isdigit():
        result = device_key(Path('/sys/class/sound') / ('card' + card) / 'device')
        if result:
            return result
    path = str(properties.get('sysfs.path', ''))
    if path.startswith('/devices/'):
        return device_key('/sys' + path)
    return ''


def matching_audio(video_id, candidates):
    target = video_usb(video_id)
    if not target:
        return ''
    try:
        proc = subprocess.run(['pactl', '-f', 'json', 'list', 'sources'],
                              capture_output=True, text=True, timeout=3)
        if proc.returncode:
            return ''
        sources = json.loads(proc.stdout)
        available = {c['id'] for c in candidates}
        matches = []
        for source in sources:
            name = source.get('name', '')
            if name not in available or name.endswith('.monitor'):
                continue
            if source_usb(source.get('properties') or {}) == target:
                matches.append(name)
        # Ambiguous profiles require an explicit choice instead of taking the first.
        return matches[0] if len(matches) == 1 else ''
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return ''


# ---- Nur Capture-Karten (keine Webcams) -----------------------------------------------------------
# Hersteller, die (fast) nur Capture-Karten bauen bzw. deren Karten hier gemeint sind
CAPTURE_VENDORS = {
    "0fd9": "Elgato",            # HD60 S/X, Cam Link, 4K60 S+/X … (Stream Decks haben kein Video)
    "07ca": "AVerMedia",         # Live Gamer Mini (GC311), Portable, Ultra …
    "534d": "MacroSilicon",      # günstige HDMI-Grabber („USB Video“)
    "2935": "Magewell",
    "1edb": "Blackmagic",
    "1164": "Yuan",
    "345f": "UGREEN/Genki",
}
CAPTURE_PCI_VENDORS = {"0x1cfa": "Elgato", "0x1461": "AVerMedia", "0x1cd7": "Magewell", "0x12ab": "Yuan"}
CAPTURE_WORDS = ("capture", "cam link", "hd60", "4k60", "live gamer", "gc311", "gc5", "gc3", "grabber",
                 "hdmi", "usb video", "game capture", "magewell", "decklink")
WEBCAM_WORDS = ("webcam", "integrated", "facetime", "c920", "c922", "brio", "kiyo", "streamcam", "ir camera")


def _read(p):
    try:
        return Path(p).read_text().strip()
    except OSError:
        return ""


def capture_card(device, sysfs=Path('/sys/class/video4linux')):
    """Ist /dev/videoN eine Capture-Karte (und keine Webcam)? Rückgabe: Herstellername oder ''."""
    name = Path(str(device)).name
    if not re.fullmatch(r'video\d+', name):
        return ''
    node = sysfs / name
    label = _read(node / 'name').lower()
    if any(w in label for w in ("gibeon kamera", "orbit kamera", "creative kamera", "obs", "virtuelle", "dummy", "loopback")):
        return ''
    try:
        dev = (node / 'device').resolve(strict=True)
    except (OSError, RuntimeError):
        dev = None
    if dev is not None:
        for d in (dev, *dev.parents):
            vid = _read(d / 'idVendor').lower()
            if vid:
                if vid in CAPTURE_VENDORS:
                    return CAPTURE_VENDORS[vid]
                break
            ven = _read(d / 'vendor').lower()
            if ven and (d / 'class').exists():
                if ven in CAPTURE_PCI_VENDORS:
                    return CAPTURE_PCI_VENDORS[ven]
                break
    if any(w in label for w in WEBCAM_WORDS):
        return ''
    return 'Capture-Karte' if any(w in label for w in CAPTURE_WORDS) else ''


# ---- Doppelter Ton (Echo/Pfeifen) ----------------------------------------------------------------
MONITOR_TAG = "gibeon-capture-mithoeren"       # Name der eigenen Wiedergabe (ffmpeg) – wiedererkennbar


def stale_monitors(ps_text, own_pid=0):
    """PIDs übrig gebliebener eigener Wiedergaben (z. B. nach einem Absturz von Capture)."""
    pids = []
    for line in ps_text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit() and MONITOR_TAG in parts[1] and "ffmpeg" in parts[1]:
            pid = int(parts[0])
            if pid != own_pid:
                pids.append(pid)
    return pids


def other_players(sink_inputs, source_name):
    """Programme, die den Ton derselben Capture-Karte schon abspielen (→ Echo).
    sink_inputs: pactl -f json list sink-inputs; source_name: PipeWire-Name der Tonquelle."""
    names = []
    for si in sink_inputs or []:
        props = si.get("properties") or {}
        app = str(props.get("application.name") or props.get("node.name") or "")
        media = str(props.get("media.name") or "")
        target = str(props.get("node.target") or props.get("target.object") or "")
        label = f"{app} {media}"
        if MONITOR_TAG in label or app.startswith("Capture"):
            continue
        if "Mithören" in label or (source_name and source_name in target) or "loopback" in label.lower():
            nice = "Studio (Mithören)" if "Mithören" in label else (app or media or "ein anderes Programm")
            if nice not in names:
                names.append(nice)
    return names


def is_capture_audio(source_name, video_id):
    """Gehört die gewählte Tonquelle zur Capture-Karte (gleiches Gerät)? Sonst z. B. ein Mikrofon."""
    target = video_usb(video_id)
    if not target or not source_name:
        return True
    try:
        proc = subprocess.run(['pactl', '-f', 'json', 'list', 'sources'], capture_output=True, text=True, timeout=3)
        for source in json.loads(proc.stdout or "[]"):
            if source.get('name') == source_name:
                return source_usb(source.get('properties') or {}) == target
    except (OSError, ValueError, subprocess.SubprocessError):
        return True
    return True


def _usb_vendor(key):
    """idVendor des USB-Geräts (Pfad aus device_key) – '' wenn unbekannt."""
    if key and not key.startswith("pci:"):
        return _read(Path(key) / "idVendor").lower()
    return ""


def _usb_label(key):
    if key and not key.startswith("pci:"):
        return (_read(Path(key) / "manufacturer") + " " + _read(Path(key) / "product")).lower()
    return ""


def capture_audio_source(props, video_target=""):
    """Gehört diese Tonquelle zu einer Capture-Karte? Webcam- und andere Mikrofone: nein.
    props: PipeWire-Eigenschaften der Quelle (pactl list sources)."""
    key = source_usb(props)
    if video_target and key and key == video_target:
        return True
    text = " ".join(str(props.get(k, "")) for k in ("device.description", "device.product.name", "alsa.card_name",
                                                       "device.vendor.name", "node.description")).lower()
    text += " " + _usb_label(key)
    if any(w in text for w in WEBCAM_WORDS) or any(w in text for w in ("webcam", "camera", "kamera", "powerconf")):
        return False
    if key.startswith("pci:"):
        return True                      # PCIe-Karten: Ton liegt auf demselben Steckplatz (siehe pci_parent)
    vid = _usb_vendor(key) or str(props.get("device.vendor.id", "")).lower().replace("0x", "")
    if vid in CAPTURE_VENDORS:
        return True
    return any(w in text for w in CAPTURE_WORDS)


def capture_audio_ids(video_id=""):
    """PipeWire-Namen aller Tonquellen, die zu Capture-Karten gehören (keine Mikrofone, keine Webcams)."""
    target = video_usb(video_id) if video_id else ""
    try:
        proc = subprocess.run(['pactl', '-f', 'json', 'list', 'sources'], capture_output=True, text=True, timeout=3)
        sources = json.loads(proc.stdout or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    out = []
    for source in sources:
        name = source.get("name", "")
        if not name or name.endswith(".monitor"):
            continue
        if capture_audio_source(source.get("properties") or {}, target):
            out.append(name)
    return out
