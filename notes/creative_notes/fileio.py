"""Dateien lesen und schreiben – mit Kodierung und Zeilenende wie in Notepad++."""

import os
import subprocess
import tempfile
from pathlib import Path

ENCODINGS = [
    # (Schlüssel, Anzeige, Python-Codec, BOM)
    ("utf-8", "UTF-8", "utf-8", b""),
    ("utf-8-bom", "UTF-8 mit BOM", "utf-8", b"\xef\xbb\xbf"),
    ("utf-16-le", "UTF-16 LE", "utf-16-le", b"\xff\xfe"),
    ("utf-16-be", "UTF-16 BE", "utf-16-be", b"\xfe\xff"),
    ("cp1252", "ANSI (Windows-1252)", "cp1252", b""),
    ("latin-1", "ISO-8859-1", "latin-1", b""),
]
ENC = {k: (label, codec, bom) for k, label, codec, bom in ENCODINGS}

EOLS = {"lf": ("\n", "Unix (LF)"), "crlf": ("\r\n", "Windows (CR LF)"), "cr": ("\r", "Macintosh (CR)")}

MAX_SIZE = 200 * 1024 * 1024


class FileTooBig(Exception):
    pass


class BinaryFile(Exception):
    pass


def detect_eol(text):
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf >= lf and crlf >= cr and crlf:
        return "crlf"
    if cr > lf:
        return "cr"
    return "lf"


def decode(raw):
    """→ (text, encoding_key). Erkennt BOM, sonst UTF-8, sonst Windows-1252."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace"), "utf-8-bom"
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="replace"), "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace"), "utf-16-be"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1"


def looks_binary(raw):
    sample = raw[:8192]
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return False
    return b"\x00" in sample


def read_file(path, force=False):
    """→ dict(text, encoding, eol). text hat immer \\n als Zeilenende."""
    p = Path(path)
    size = p.stat().st_size
    if size > MAX_SIZE and not force:
        raise FileTooBig(size)
    raw = p.read_bytes()
    if looks_binary(raw) and not force:
        raise BinaryFile()
    text, enc = decode(raw)
    eol = detect_eol(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return {"text": text, "encoding": enc, "eol": eol}


def reinterpret(path, encoding):
    """Datei mit einer anderen Kodierung neu lesen (Menü „Kodierung“)."""
    raw = Path(path).read_bytes()
    label, codec, bom = ENC[encoding]
    if bom and raw.startswith(bom):
        raw = raw[len(bom):]
    text = raw.decode(codec, errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def encode(text, encoding, eol):
    label, codec, bom = ENC.get(encoding, ENC["utf-8"])
    text = text.replace("\n", EOLS.get(eol, EOLS["lf"])[0])
    return bom + text.encode(codec, errors="replace")


def unencodable(text, encoding):
    """True, wenn Zeichen in dieser Kodierung verloren gingen."""
    codec = ENC.get(encoding, ENC["utf-8"])[1]
    try:
        text.encode(codec)
        return False
    except UnicodeEncodeError:
        return True


def write_file(path, text, encoding, eol):
    """Sicher speichern: erst in eine Hilfsdatei, dann austauschen (Rechte bleiben)."""
    data = encode(text, encoding, eol)
    p = Path(path)
    mode = None
    try:
        mode = p.stat().st_mode & 0o7777
    except FileNotFoundError:
        pass
    if p.is_symlink():
        p = p.resolve()
    fd, tmp = tempfile.mkstemp(prefix=".~" + p.name + ".", dir=str(p.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_file_as_admin(path, text, encoding, eol):
    """Speichern mit Administratorrechten (z. B. Dateien in /etc)."""
    data = encode(text, encoding, eol)
    r = subprocess.run(["pkexec", "/usr/bin/tee", str(path)], input=data,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)
    if r.returncode != 0:
        raise PermissionError(r.stderr.decode(errors="replace").strip() or "abgebrochen")
