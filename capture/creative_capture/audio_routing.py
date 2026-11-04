"""Associate video and audio by physical USB device, never by generic names."""
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


def video_usb(device):
    name = Path(device).name
    if not re.fullmatch(r'video\d+', name):
        return ''
    return usb_parent(Path('/sys/class/video4linux') / name / 'device')


def source_usb(properties):
    card = str(properties.get('alsa.card', properties.get('api.alsa.card', '')))
    if card.isdigit():
        result = usb_parent(Path('/sys/class/sound') / ('card' + card) / 'device')
        if result:
            return result
    path = str(properties.get('sysfs.path', ''))
    if path.startswith('/devices/'):
        return usb_parent('/sys' + path)
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
