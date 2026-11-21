"""Wayland-Protokoll lesen und schreiben – nur Standardbibliothek.

Die Nachrichtenformate kommen aus den XML-Beschreibungen, die mit wayland-devel und
wayland-protocols-devel ins System kommen (/usr/share/wayland, /usr/share/wayland-protocols).
So muss der Vermittler (fenster.py) keine Formate fest eingebaut haben.

Aufbau einer Nachricht: Objekt-ID (u32), dann (Länge << 16 | Opcode) (u32), dann die Argumente.
Dateideskriptoren („fd“) reisen nicht im Datenstrom, sondern nebenher (SCM_RIGHTS).
"""

import struct
import xml.etree.ElementTree as ET
from pathlib import Path

PROTO_DIRS = ("/usr/share/wayland", "/usr/share/wayland-protocols")
SERVER_ID_START = 0xFF000000
HEADER = struct.Struct("=II")
U32 = struct.Struct("=I")
I32 = struct.Struct("=i")


class Message:
    __slots__ = ("name", "args")

    def __init__(self, name, args):
        self.name = name
        self.args = args          # [(typ, interface oder None)]

    @property
    def nfds(self):
        return sum(1 for t, _ in self.args if t == "fd")


class Interface:
    __slots__ = ("name", "version", "requests", "events")

    def __init__(self, name, version):
        self.name = name
        self.version = version
        self.requests = []
        self.events = []

    def opcode(self, kind, name):
        msgs = self.requests if kind == "request" else self.events
        for i, m in enumerate(msgs):
            if m.name == name:
                return i
        raise KeyError(f"{self.name}.{name}")


def load_protocols(dirs=PROTO_DIRS):
    """Alle Schnittstellen aus den XML-Dateien. Gleicher Name doppelt → höchste Version."""
    ifaces = {}
    for d in dirs:
        root = Path(d)
        if not root.is_dir():
            continue
        for f in sorted(root.rglob("*.xml")):
            try:
                tree = ET.parse(f)
            except (ET.ParseError, OSError):
                continue
            for el in tree.getroot().iter("interface"):
                name = el.get("name")
                try:
                    version = int(el.get("version", "1"))
                except ValueError:
                    continue
                if not name or (name in ifaces and ifaces[name].version >= version):
                    continue
                iface = Interface(name, version)
                for kind, target in (("request", iface.requests), ("event", iface.events)):
                    for m in el.findall(kind):
                        target.append(Message(m.get("name"), [(a.get("type"), a.get("interface"))
                                                              for a in m.findall("arg")]))
                ifaces[name] = iface
    return ifaces


def _pad(n):
    return (n + 3) & ~3


class Incomplete(Exception):
    """Es fehlen noch Daten oder Dateideskriptoren."""


def decode(msg, data, fds):
    """Argumente einer Nachricht (ohne Kopf) lesen. fds: Liste, aus der fd-Argumente
    entnommen werden (nur gelesen – entfernt wird erst, wenn alles passt)."""
    out = []
    pos = 0
    fd_i = 0
    for typ, iface in msg.args:
        if typ == "fd":
            if fd_i >= len(fds):
                raise Incomplete()
            out.append(fds[fd_i])
            fd_i += 1
            continue
        if typ in ("int", "fixed"):
            out.append(I32.unpack_from(data, pos)[0])
            pos += 4
        elif typ in ("uint", "object"):
            out.append(U32.unpack_from(data, pos)[0])
            pos += 4
        elif typ == "new_id":
            if iface:
                out.append(U32.unpack_from(data, pos)[0])
                pos += 4
            else:                                   # wl_registry.bind: Schnittstelle, Version, ID
                s, pos = _read_string(data, pos)
                ver = U32.unpack_from(data, pos)[0]
                nid = U32.unpack_from(data, pos + 4)[0]
                pos += 8
                out.append((s, ver, nid))
        elif typ == "string":
            s, pos = _read_string(data, pos)
            out.append(s)
        elif typ == "array":
            n = U32.unpack_from(data, pos)[0]
            out.append(bytes(data[pos + 4:pos + 4 + n]))
            pos += 4 + _pad(n)
        else:
            raise ValueError(f"unbekannter Typ {typ}")
    if pos != len(data):
        raise ValueError("Länge passt nicht zur Beschreibung")
    return out, fd_i


def _read_string(data, pos):
    n = U32.unpack_from(data, pos)[0]
    if n == 0:
        return None, pos + 4
    raw = bytes(data[pos + 4:pos + 4 + n - 1])
    return raw.decode("utf-8", "replace"), pos + 4 + _pad(n)


def _write_string(s):
    if s is None:
        return U32.pack(0)
    raw = s.encode("utf-8") + b"\0"
    return U32.pack(len(raw)) + raw + b"\0" * (_pad(len(raw)) - len(raw))


def encode(obj, opcode, msg, values):
    """Nachricht samt Kopf bauen. Liefert (bytes, [fds in Reihenfolge])."""
    body = bytearray()
    fds = []
    for (typ, iface), v in zip(msg.args, values):
        if typ == "fd":
            fds.append(v)
        elif typ in ("int", "fixed"):
            body += I32.pack(v)
        elif typ in ("uint", "object"):
            body += U32.pack(v)
        elif typ == "new_id":
            if iface:
                body += U32.pack(v)
            else:
                s, ver, nid = v
                body += _write_string(s) + U32.pack(ver) + U32.pack(nid)
        elif typ == "string":
            body += _write_string(v)
        elif typ == "array":
            body += U32.pack(len(v)) + v + b"\0" * (_pad(len(v)) - len(v))
    size = 8 + len(body)
    return HEADER.pack(obj, (size << 16) | opcode) + bytes(body), fds


def split(buf):
    """Vollständige Nachrichten aus einem Puffer: [(obj, opcode, body)], Rest."""
    out = []
    pos = 0
    while len(buf) - pos >= 8:
        obj, word = HEADER.unpack_from(buf, pos)
        size = word >> 16
        if size < 8:
            raise ValueError("kaputte Nachricht")
        if len(buf) - pos < size:
            break
        out.append((obj, word & 0xFFFF, bytes(buf[pos + 8:pos + size])))
        pos += size
    return out, buf[pos:]
