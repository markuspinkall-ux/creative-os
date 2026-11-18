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
