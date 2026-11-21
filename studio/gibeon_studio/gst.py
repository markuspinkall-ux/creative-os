"""Schlanke Anbindung an GStreamer über ctypes (ohne PyGObject).

Studio braucht nur wenig von GStreamer: Pipelines aus Beschreibungen bauen, Eigenschaften setzen,
Pads verbinden, Meldungen vom Bus lesen und Vorschaubilder abholen. Das geht direkt über die
C-Bibliothek – so läuft derselbe Code im System und in den Tests.
"""

import ctypes
import ctypes.util
import threading

_lib = {}


def _load(name, soname):
    path = ctypes.util.find_library(name) or soname
    return ctypes.CDLL(path)


gst = _load("gstreamer-1.0", "libgstreamer-1.0.so.0")
gobj = _load("gobject-2.0", "libgobject-2.0.so.0")
glib = _load("glib-2.0", "libglib-2.0.so.0")
app = _load("gstapp-1.0", "libgstapp-1.0.so.0")

P = ctypes.c_void_p
S = ctypes.c_char_p
U64 = ctypes.c_uint64
I64 = ctypes.c_int64


def _fn(lib, name, res, *args):
    f = getattr(lib, name)
    f.restype = res
    f.argtypes = list(args)
    return f


class GError(ctypes.Structure):
    _fields_ = [("domain", ctypes.c_uint32), ("code", ctypes.c_int), ("message", S)]


class MapInfo(ctypes.Structure):
    _fields_ = [("memory", P), ("flags", ctypes.c_int), ("data", ctypes.POINTER(ctypes.c_ubyte)),
                ("size", ctypes.c_size_t), ("maxsize", ctypes.c_size_t),
                ("user_data", P * 4), ("_reserved", P * 4)]


init_check = _fn(gst, "gst_init_check", ctypes.c_int, P, P, P)
parse_launch = _fn(gst, "gst_parse_launch", P, S, ctypes.POINTER(ctypes.POINTER(GError)))
parse_bin = _fn(gst, "gst_parse_bin_from_description", P, S, ctypes.c_int, ctypes.POINTER(ctypes.POINTER(GError)))
factory_find = _fn(gst, "gst_element_factory_find", P, S)
factory_make = _fn(gst, "gst_element_factory_make", P, S, S)
set_state = _fn(gst, "gst_element_set_state", ctypes.c_int, P, ctypes.c_int)
get_state = _fn(gst, "gst_element_get_state", ctypes.c_int, P, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), U64)
bin_by_name = _fn(gst, "gst_bin_get_by_name", P, P, S)
bin_add = _fn(gst, "gst_bin_add", ctypes.c_int, P, P)
bin_remove = _fn(gst, "gst_bin_remove", ctypes.c_int, P, P)
sync_state = _fn(gst, "gst_element_sync_state_with_parent", ctypes.c_int, P)
get_bus = _fn(gst, "gst_element_get_bus", P, P)
bus_pop = _fn(gst, "gst_bus_timed_pop_filtered", P, P, U64, ctypes.c_int)
static_pad = _fn(gst, "gst_element_get_static_pad", P, P, S)
request_pad = _fn(gst, "gst_element_request_pad_simple", P, P, S)
release_pad = _fn(gst, "gst_element_release_request_pad", None, P, P)
pad_link = _fn(gst, "gst_pad_link", ctypes.c_int, P, P)
pad_unlink = _fn(gst, "gst_pad_unlink", ctypes.c_int, P, P)
pad_set_offset = _fn(gst, "gst_pad_set_offset", None, P, I64)
pad_send_event = _fn(gst, "gst_pad_send_event", ctypes.c_int, P, P)
PROBE_CB = ctypes.CFUNCTYPE(ctypes.c_int, P, P, P)
pad_add_probe = _fn(gst, "gst_pad_add_probe", ctypes.c_ulong, P, ctypes.c_int, PROBE_CB, P, P)
pad_remove_probe = _fn(gst, "gst_pad_remove_probe", None, P, ctypes.c_ulong)
event_new_eos = _fn(gst, "gst_event_new_eos", P)
element_send_event = _fn(gst, "gst_element_send_event", ctypes.c_int, P, P)
object_unref = _fn(gst, "gst_object_unref", None, P)
object_name = _fn(gst, "gst_object_get_name", P, P)
mini_unref = _fn(gst, "gst_mini_object_unref", None, P)
set_object_arg = _fn(gst, "gst_util_set_object_arg", None, P, S, S)
element_clock = _fn(gst, "gst_element_get_clock", P, P)
clock_time = _fn(gst, "gst_clock_get_time", U64, P)
base_time = _fn(gst, "gst_element_get_base_time", U64, P)
msg_structure = _fn(gst, "gst_message_get_structure", P, P)
structure_to_string = _fn(gst, "gst_structure_to_string", P, P)
structure_name = _fn(gst, "gst_structure_get_name", S, P)
parse_error = _fn(gst, "gst_message_parse_error", None, P, ctypes.POINTER(ctypes.POINTER(GError)), ctypes.POINTER(P))
parse_warning = _fn(gst, "gst_message_parse_warning", None, P, ctypes.POINTER(ctypes.POINTER(GError)), ctypes.POINTER(P))
pull_sample = _fn(app, "gst_app_sink_try_pull_sample", P, P, U64)
sample_buffer = _fn(gst, "gst_sample_get_buffer", P, P)
sample_caps = _fn(gst, "gst_sample_get_caps", P, P)
caps_structure = _fn(gst, "gst_caps_get_structure", P, P, ctypes.c_uint)
structure_get_int = _fn(gst, "gst_structure_get_int", ctypes.c_int, P, S, ctypes.POINTER(ctypes.c_int))
buffer_map = _fn(gst, "gst_buffer_map", ctypes.c_int, P, ctypes.POINTER(MapInfo), ctypes.c_int)
buffer_unmap = _fn(gst, "gst_buffer_unmap", None, P, ctypes.POINTER(MapInfo))
g_free = _fn(glib, "g_free", None, P)
g_error_free = _fn(glib, "g_error_free", None, P)
class_find_property = _fn(gobj, "g_object_class_find_property", P, P, S)

STATE_NULL, STATE_READY, STATE_PAUSED, STATE_PLAYING = 1, 2, 3, 4
MSG_EOS, MSG_ERROR, MSG_WARNING, MSG_ELEMENT = 1 << 0, 1 << 1, 1 << 2, 1 << 15
PROBE_BLOCK_DOWNSTREAM = (1 << 1) | (1 << 4) | (1 << 5)   # BLOCK | BUFFER | BUFFER_LIST
PROBE_EVENT_DOWNSTREAM = 1 << 6
PROBE_OK, PROBE_REMOVE = 1, 2
MAP_READ = 1
SECOND = 1_000_000_000

_ready = False
_keep = []                       # Rückruffunktionen am Leben halten
_lock = threading.Lock()


message_new_eos = _fn(gst, "gst_message_new_eos", P, P)


def init():
    global _ready, EVENT_EOS
    if not _ready:
        if not init_check(None, None, None):
            raise RuntimeError("GStreamer lässt sich nicht starten")
        m = message_new_eos(None)
        ok = _type_after_mini(m) == MSG_EOS
        mini_unref(m)
        if not ok:
            raise RuntimeError("GStreamer-Aufbau unerwartet (MiniObject)")
        e = event_new_eos()
        EVENT_EOS = _type_after_mini(e)
        mini_unref(e)
        _ready = True


def has(factory):
    init()
    f = factory_find(factory.encode())
    if f:
        object_unref(f)
        return True
    return False


def has_property(element, name):
    klass = ctypes.cast(element, ctypes.POINTER(P))[0]       # G_OBJECT_GET_CLASS
    return bool(class_find_property(klass, name.encode()))


def set_prop(obj, name, value):
    """Eigenschaft setzen (Text wird passend umgewandelt). Unbekannte Eigenschaften überspringen."""
    if obj and has_property(obj, name):
        if isinstance(value, bool):
            value = "true" if value else "false"
        set_object_arg(obj, name.encode(), str(value).encode())
        return True
    return False


def _error(err):
    msg = err.contents.message.decode("utf-8", "replace") if err and err.contents.message else "unbekannt"
    g_error_free(err)
    return msg


def launch(desc):
    init()
    err = ctypes.POINTER(GError)()
    el = parse_launch(desc.encode(), ctypes.byref(err))
    if err:
        msg = _error(err)
        if el:
            object_unref(el)
        raise ValueError(msg)
    return el


def make_bin(desc):
    init()
    err = ctypes.POINTER(GError)()
    el = parse_bin(desc.encode(), 1, ctypes.byref(err))
    if err:
        msg = _error(err)
        if el:
            object_unref(el)
        raise ValueError(msg)
    return el


def name_of(obj):
    p = object_name(obj)
    if not p:
        return ""
    s = ctypes.string_at(p).decode()
    g_free(p)
    return s


def running_time(pipeline):
    clk = element_clock(pipeline)
    if not clk:
        return 0
    t = clock_time(clk) - base_time(pipeline)
    object_unref(clk)
    return t


def probe(pad, mask, fn):
    """fn(pad, info) → PROBE_OK/PROBE_REMOVE. Läuft im GStreamer-Thread."""
    cb = PROBE_CB(lambda p, info, _u: fn(p, info))
    with _lock:
        _keep.append(cb)
    return pad_add_probe(pad, mask, cb, None, None)


class _ProbeInfo(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("id", ctypes.c_ulong), ("data", P)]


# GstMiniObject: GType type; gint refcount, lockstate; guint flags; copy, dispose, free; guint priv_uint;
# gpointer priv_pointer – auf 64-Bit-Systemen 64 Byte. Wird in init() mit echten Objekten geprüft.
MINI = 64
EVENT_EOS = None


def _type_after_mini(ptr):
    return ctypes.cast(ptr + MINI, ctypes.POINTER(ctypes.c_int)).contents.value


def probe_is_eos(info):
    ev = ctypes.cast(info, ctypes.POINTER(_ProbeInfo)).contents.data
    return bool(ev) and _type_after_mini(ev) == EVENT_EOS


def pop(bus):
    """Nächste Meldung (Typ, Quelle, Text/Struktur) oder None."""
    m = bus_pop(bus, 0, MSG_EOS | MSG_ERROR | MSG_WARNING | MSG_ELEMENT)
    if not m:
        return None
    # GstMessage: GstMiniObject, type (int), timestamp (u64), src (GstObject*)
    class Msg(ctypes.Structure):
        _fields_ = [("mini", ctypes.c_ubyte * MINI), ("type", ctypes.c_int),
                    ("timestamp", U64), ("src", P)]
    info = ctypes.cast(m, ctypes.POINTER(Msg)).contents
    typ, src = info.type, info.src
    src_name = name_of(src) if src else ""
    text = ""
    if typ in (MSG_ERROR, MSG_WARNING):
        err = ctypes.POINTER(GError)()
        dbg = P()
        (parse_error if typ == MSG_ERROR else parse_warning)(m, ctypes.byref(err), ctypes.byref(dbg))
        text = _error(err) if err else ""
        if dbg:
            text += " | " + ctypes.string_at(dbg).decode("utf-8", "replace")
            g_free(dbg)
    elif typ == MSG_ELEMENT:
        st = msg_structure(m)
        if st:
            p = structure_to_string(st)
            text = ctypes.string_at(p).decode("utf-8", "replace")
            g_free(p)
    mini_unref(m)
    return typ, src_name, text


def pull_frame(appsink, blocking=False):
    """Neuestes Vorschaubild als (bytes, breite, höhe) oder None."""
    s = pull_sample_blocking(appsink) if blocking else pull_sample(appsink, 0)
    if not s:
        return None
    try:
        caps = sample_caps(s)
        st = caps_structure(caps, 0) if caps else None
        w, h = ctypes.c_int(), ctypes.c_int()
        if not st or not structure_get_int(st, b"width", ctypes.byref(w)) or \
                not structure_get_int(st, b"height", ctypes.byref(h)):
            return None
        buf = sample_buffer(s)
        info = MapInfo()
        if not buf_map(buf, info):
            return None
        try:
            data = ctypes.string_at(info.data, info.size)
        finally:
            buffer_unmap(buf, ctypes.byref(info))
        return data, w.value, h.value
    finally:
        mini_unref(s)


def buf_map(buf, info):
    return bool(buffer_map(buf, ctypes.byref(info), MAP_READ))


# ---- Ausgänge: Puffer aus dem Mischpult in eigene Pipelines geben (appsink → appsrc) ----------
SAMPLE_CB = ctypes.CFUNCTYPE(ctypes.c_int, P, P)
signal_connect = _fn(gobj, "g_signal_connect_data", ctypes.c_ulong, P, S, SAMPLE_CB, P, P, ctypes.c_int)
signal_disconnect = _fn(gobj, "g_signal_handler_disconnect", None, P, ctypes.c_ulong)
pull_sample_blocking = _fn(app, "gst_app_sink_pull_sample", P, P)
appsrc_push_buffer = _fn(app, "gst_app_src_push_buffer", ctypes.c_int, P, P)
appsrc_set_caps = _fn(app, "gst_app_src_set_caps", None, P, P)
appsrc_eos = _fn(app, "gst_app_src_end_of_stream", ctypes.c_int, P)
buffer_copy = _fn(gst, "gst_buffer_copy", P, P)
FLOW_OK = 0
NONE_TIME = 0xFFFFFFFFFFFFFFFF


class _BufferHead(ctypes.Structure):
    # GstBuffer: GstMiniObject, GstBufferPool *pool, pts, dts, duration, offset, offset_end
    _fields_ = [("mini", ctypes.c_ubyte * MINI), ("pool", P), ("pts", U64), ("dts", U64),
                ("duration", U64), ("offset", U64), ("offset_end", U64)]


def connect_new_sample(appsink, fn):
    """fn(appsink) wird im GStreamer-Thread für jedes neue Bild/Tonstück aufgerufen."""
    cb = SAMPLE_CB(lambda sink, _u: fn(sink))
    with _lock:
        _keep.append(cb)
    return signal_connect(appsink, b"new-sample", cb, None, None, 0)


def forward_sample(appsink, appsrc, start, caps_done):
    """Ein Stück vom Mischpult holen und zeitlich verschoben an einen Ausgang geben.
    start: Startzeit des Ausgangs (Laufzeit im Mischpult) – davor Liegendes wird verworfen.
    Rückgabe: (caps gesetzt?, pts des Stücks oder None)."""
    s = pull_sample_blocking(appsink)
    if not s:
        return caps_done, None
    try:
        buf = sample_buffer(s)
        head = ctypes.cast(buf, ctypes.POINTER(_BufferHead)).contents
        pts = head.pts
        if appsrc is None or pts == NONE_TIME or pts < start:
            return caps_done, pts
        if not caps_done:
            caps = sample_caps(s)
            if caps:
                appsrc_set_caps(appsrc, caps)
                caps_done = True
        out = buffer_copy(buf)                       # teilt die Daten, nur die Zeiten sind eigene
        oh = ctypes.cast(out, ctypes.POINTER(_BufferHead)).contents
        oh.pts = pts - start
        if oh.dts != NONE_TIME:
            oh.dts = max(0, oh.dts - start)
        appsrc_push_buffer(appsrc, out)              # übernimmt den Puffer
        return caps_done, pts
    finally:
        mini_unref(s)


# ---- Abgerundete Ecken (cairooverlay) und Pads im laufenden Betrieb -------------------------------
DRAW_CB = ctypes.CFUNCTYPE(None, P, P, U64, U64, P)
signal_connect_any = _fn(gobj, "g_signal_connect_data", ctypes.c_ulong, P, S, P, P, P, ctypes.c_int)
pad_get_name = object_name
try:
    cairo = _load("cairo", "libcairo.so.2")
    c_set_operator = _fn(cairo, "cairo_set_operator", None, P, ctypes.c_int)
    c_set_fill_rule = _fn(cairo, "cairo_set_fill_rule", None, P, ctypes.c_int)
    c_rectangle = _fn(cairo, "cairo_rectangle", None, P, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double)
    c_new_sub_path = _fn(cairo, "cairo_new_sub_path", None, P)
    c_arc = _fn(cairo, "cairo_arc", None, P, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double)
    c_close_path = _fn(cairo, "cairo_close_path", None, P)
    c_fill = _fn(cairo, "cairo_fill", None, P)
except OSError:
    cairo = None


def clear_corners(cr, w, h, r):
    """Ecken außerhalb eines abgerundeten Rechtecks durchsichtig machen."""
    import math
    r = max(0.0, min(r, w / 2, h / 2))
    if r <= 0 or not cairo:
        return
    c_set_operator(cr, 0)                 # CAIRO_OPERATOR_CLEAR
    c_set_fill_rule(cr, 1)                # EVEN_ODD: außen minus innen
    c_rectangle(cr, 0, 0, w, h)
    c_new_sub_path(cr)
    c_arc(cr, w - r, r, r, -math.pi / 2, 0)
    c_arc(cr, w - r, h - r, r, 0, math.pi / 2)
    c_arc(cr, r, h - r, r, math.pi / 2, math.pi)
    c_arc(cr, r, r, r, math.pi, 1.5 * math.pi)
    c_close_path(cr)
    c_fill(cr)


def connect_draw(overlay, fn):
    """fn(cairo_t) für jedes Bild von cairooverlay (GStreamer-Thread)."""
    cb = DRAW_CB(lambda _el, cr, _ts, _dur, _u: fn(cr))
    with _lock:
        _keep.append(cb)
    return signal_connect_any(overlay, b"draw", ctypes.cast(cb, P), None, None, 0)


def pad_name(pad):
    return name_of(pad)


def relay_sample(appsink, appsrc):
    """Ein Bild von einer Zuliefer-Pipeline ins Mischpult geben. Die Zeit setzt das Mischpult
    selbst (appsrc do-timestamp), deshalb werden die Zeitstempel gelöscht."""
    s = pull_sample_blocking(appsink)
    if not s:
        return
    try:
        if appsrc is None:
            return
        out = buffer_copy(sample_buffer(s))
        head = ctypes.cast(out, ctypes.POINTER(_BufferHead)).contents
        head.pts = head.dts = head.duration = NONE_TIME
        appsrc_push_buffer(appsrc, out)
    finally:
        mini_unref(s)


g_object_get_u64 = _fn(gobj, "g_object_get", None, P, S, ctypes.POINTER(U64), P)


def get_u64(obj, name):
    """Zahl-Eigenschaft (guint64) lesen, z. B. „current-level-time“ einer queue. 0, wenn es sie nicht gibt."""
    if not obj or not has_property(obj, name):
        return 0
    v = U64(0)
    g_object_get_u64(obj, name.encode(), ctypes.byref(v), None)
    return v.value


buffer_new_allocate = _fn(gst, "gst_buffer_new_allocate", P, P, ctypes.c_size_t, P)
buffer_fill = _fn(gst, "gst_buffer_fill", ctypes.c_size_t, P, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t)


def push_bytes(appsrc, data):
    """Fertige Bilddaten (z. B. eine Browserquelle) in eine appsrc geben."""
    buf = buffer_new_allocate(None, len(data), None)
    if not buf:
        return False
    buffer_fill(buf, 0, data, len(data))
    return appsrc_push_buffer(appsrc, buf) == FLOW_OK
