"""Was kann die Webcam? Liest Formate, Auflösungen und Bildraten direkt per V4L2.

Ohne Zusatzprogramme (kein v4l2-ctl nötig): nur ioctl über fcntl.
"""

import fcntl
import os
import struct

_IOC_READWRITE = 3


def _iowr(nr, size):
    return (_IOC_READWRITE << 30) | (size << 16) | (ord("V") << 8) | nr


_FMTDESC = "<III32sII3I"            # 64 Bytes
_FRMSIZE = "<III6I2I"               # 44 Bytes
_FRMIVAL = "<IIIII6I2I"             # 52 Bytes
VIDIOC_ENUM_FMT = _iowr(2, struct.calcsize(_FMTDESC))
VIDIOC_ENUM_FRAMESIZES = _iowr(74, struct.calcsize(_FRMSIZE))
VIDIOC_ENUM_FRAMEINTERVALS = _iowr(75, struct.calcsize(_FRMIVAL))
BUF_TYPE_VIDEO_CAPTURE = 1
DISCRETE = 1


def fourcc(code):
    return struct.pack("<I", code).decode("ascii", "replace").strip()


def _code(text):
    return struct.unpack("<I", text.encode("ascii"))[0]


def _ioctl(fd, req, fmt, values):
    buf = bytearray(struct.pack(fmt, *values))
    fcntl.ioctl(fd, req, buf, True)
    return struct.unpack(fmt, bytes(buf))


def _rates(fd, pix, w, h):
    out = []
    for i in range(64):
        try:
            r = _ioctl(fd, VIDIOC_ENUM_FRAMEINTERVALS, _FRMIVAL, (i, pix, w, h, 0) + (0,) * 8)
        except OSError:
            break
        if r[4] == DISCRETE:
            num, den = r[5], r[6]
            if num:
                out.append(den / num)
        else:                          # stufenlos: schnellste Bildrate = kleinstes Intervall
            num, den = r[5], r[6]
            if num:
                out.append(den / num)
            break
    return out


def list_modes(device):
    """[{format, width, height, fps}] – jede Kombination, die die Kamera anbietet."""
    modes = []
    try:
        fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return modes
    try:
        for fi in range(32):
            try:
                f = _ioctl(fd, VIDIOC_ENUM_FMT, _FMTDESC, (fi, BUF_TYPE_VIDEO_CAPTURE, 0, b"", 0, 0, 0, 0, 0))
            except OSError:
                break
            pix = f[4]
            for si in range(64):
                try:
                    s = _ioctl(fd, VIDIOC_ENUM_FRAMESIZES, _FRMSIZE, (si, pix, 0) + (0,) * 8)
                except OSError:
                    break
                if s[2] == DISCRETE:
                    sizes = [(s[3], s[4])]
                else:                  # stufenlos: übliche Größen innerhalb der Grenzen
                    minw, maxw, _, minh, maxh, _ = s[3:9]
                    sizes = [(w, h) for w, h in ((1920, 1080), (1280, 720), (640, 480))
                             if minw <= w <= maxw and minh <= h <= maxh]
                for w, h in sizes:
                    for r in _rates(fd, pix, w, h):
                        modes.append({"format": fourcc(pix), "width": w, "height": h, "fps": round(r, 2)})
                if s[2] != DISCRETE:
                    break
    finally:
        os.close(fd)
    return modes


# komprimierte Formate schaffen über USB 2 hohe Auflösung *und* hohe Bildrate
_PREFERENCE = {"MJPG": 3, "H264": 1, "YUYV": 2, "NV12": 2}


def best_mode(modes, max_width=1920, max_fps=60):
    """Höchste Bildrate (bis 60) bei mindestens 720p, dann größte Auflösung bis 1080p."""
    usable = [m for m in modes if m["width"] <= max_width and m["format"] in ("MJPG", "YUYV", "NV12")]
    if not usable:
        return None
    hd = [m for m in usable if m["height"] >= 720] or usable
    top = min(max_fps, max(m["fps"] for m in hd))
    fast = [m for m in hd if m["fps"] >= top - 0.5]
    fast.sort(key=lambda m: (m["width"] * m["height"], _PREFERENCE.get(m["format"], 0)), reverse=True)
    best = dict(fast[0])
    best["fps"] = min(max_fps, best["fps"])
    return best


if __name__ == "__main__":
    import sys
    for dev in sys.argv[1:] or ["/dev/video0"]:
        ms = list_modes(dev)
        for m in ms:
            print(dev, m)
        print("beste Einstellung:", best_mode(ms))
