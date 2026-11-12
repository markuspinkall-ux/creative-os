"""Figuren für die Creative Engine: GLB lesen, Skelett (Mixamo-Namen aus Creative 3D), Bewegungen
berechnen, als animierte GLB speichern. Ohne Oberfläche, testbar.

Koordinaten wie in Creative 3D: Y oben, die Figur schaut nach +Z, ihre linke Seite liegt bei +X.
Bewegungen werden als Winkel (Grad) je Gelenk gespeichert, bezogen auf eine „Grundhaltung“:
aufrecht stehen, Arme hängen locker neben dem Körper (auch wenn das Modell in T-Pose gebaut ist).

  X-Drehung +  → Oberkörper/Kopf neigt nach vorn; Arm/Bein (hängend) schwingt nach HINTEN
  X-Drehung −  → Arm/Bein schwingt nach VORN;   Knie (LeftLeg) +  = Unterschenkel beugt nach hinten
  Z-Drehung    → seitlich: LeftArm + hebt den linken Arm nach außen, RightArm − den rechten
  Y-Drehung    → um die Hochachse (Hüfte/Kopf drehen)
"""

import json
import math
import re
import struct
import sys
from pathlib import Path

import numpy as np

try:
    import creative3d_rig as R
except ImportError:  # im Quellbaum liegt Creative 3D nebenan
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "creative3d"))
    import creative3d_rig as R

NAMES, PARENT, LABEL, INDEX, PREFIX = R.NAMES, R.PARENT, R.LABEL, R.INDEX, R.PREFIX
CHILDREN = {n: [c for c in NAMES if PARENT[c] == n] for n in NAMES}
ORDER = list(NAMES)          # Eltern stehen immer vor ihren Kindern

SLOTS = [("idle", "Stehen"), ("walk", "Gehen"), ("run", "Rennen"), ("jump", "Springen"),
         ("fall", "Fallen"), ("cheer", "Jubeln"), ("hit", "Treffer")]
ATTACK_SLOTS = [("attack1", "Angriff 1"), ("attack2", "Angriff 2"), ("attack3", "Angriff 3"), ("attack4", "Angriff 4")]
ATTACK_STYLE = {"attack1": "Schlag", "attack2": "Tritt", "attack3": "Hieb von oben", "attack4": "Wirbel"}
SLOT_NAME = dict(SLOTS + ATTACK_SLOTS)
LOOPING = {"idle", "walk", "run", "fall", "cheer"}
FPS = 24

# ---- Mathe ----------------------------------------------------------------------------------


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(deg):
    """Grad (x, y, z) → Drehmatrix; zuerst X, dann Y, dann Z."""
    x, y, z = (math.radians(float(v)) for v in deg)
    return rot_z(z) @ rot_y(y) @ rot_x(x)


def between(a, b):
    """Drehung, die Richtung a auf Richtung b bringt."""
    a = np.asarray(a, float) / max(np.linalg.norm(a), 1e-9)
    b = np.asarray(b, float) / max(np.linalg.norm(b), 1e-9)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.9999:
        axis = np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0])
        axis /= np.linalg.norm(axis)
        return 2 * np.outer(axis, axis) - np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def quat(m):
    """Drehmatrix → Quaternion [x, y, z, w]."""
    t = np.trace(m)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s]
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s]
    q = np.array(q)
    return q / np.linalg.norm(q)


# ---- GLB lesen ------------------------------------------------------------------------------

DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _accessor(gltf, binary, index):
    acc = gltf["accessors"][index]
    dtype = np.dtype(DTYPE[acc["componentType"]])
    width = WIDTH[acc["type"]]
    count = acc["count"]
    if "bufferView" not in acc:
        return np.zeros((count, width), np.float32)
    view = gltf["bufferViews"][acc["bufferView"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", 0) or dtype.itemsize * width
    raw = np.frombuffer(binary, dtype=np.uint8, count=stride * (count - 1) + dtype.itemsize * width, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(count, dtype.itemsize * width), strides=(stride, 1))
    out = np.ascontiguousarray(rows).view(dtype).reshape(count, width).astype(np.float64)
    if acc.get("normalized") and dtype.kind in "iu":
        out /= np.iinfo(dtype).max
    return out


def _node_matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"], float).reshape(4, 4).T
    m = np.eye(4)
    if "scale" in node:
        m = np.diag([*node["scale"], 1.0]) @ m
    if "rotation" in node:
        x, y, z, w = node["rotation"]
        r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        rm = np.eye(4)
        rm[:3, :3] = r
        m = rm @ m
    if "translation" in node:
        tm = np.eye(4)
        tm[:3, 3] = node["translation"]
        m = tm @ m
    return m


def _texture_sampler(gltf, binary, material):
    """Gibt eine Funktion uv → Farbe zurück (oder None)."""
    info = material.get("pbrMetallicRoughness", {}).get("baseColorTexture")
    if not info:
        return None
    try:
        from PySide6.QtGui import QImage
        tex = gltf["textures"][info["index"]]
        img = gltf["images"][tex["source"]]
        view = gltf["bufferViews"][img["bufferView"]]
        data = binary[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
        image = QImage.fromData(bytes(data))
        if image.isNull():
            return None
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        if image.width() > 1024:
            image = image.scaledToWidth(1024)
        w, h = image.width(), image.height()
        arr = np.frombuffer(image.constBits(), np.uint8, count=image.sizeInBytes()).reshape(h, image.bytesPerLine())
        arr = arr[:, :w * 4].reshape(h, w, 4).astype(np.float64) / 255.0
    except Exception:  # noqa: BLE001
        return None

    def sample(uv):
        u = np.mod(uv[:, 0], 1.0)
        v = np.mod(uv[:, 1], 1.0)
        return arr[np.clip((v * h).astype(int), 0, h - 1), np.clip((u * w).astype(int), 0, w - 1)]
    return sample


def load_mesh(path):
    """GLB → {"vertices", "faces", "colors" (RGBA 0..1), "animations": [Namen]} in Weltkoordinaten."""
    gltf, binary = R.read_glb(path)
    verts, faces, colors = [], [], []
    offset = 0

    def visit(index, parent):
        nonlocal offset
        node = gltf["nodes"][index]
        world = parent @ _node_matrix(node)
        if "mesh" in node:
            for prim in gltf["meshes"][node["mesh"]]["primitives"]:
                if prim.get("mode", 4) != 4 or "POSITION" not in prim["attributes"]:
                    continue
                pos = _accessor(gltf, binary, prim["attributes"]["POSITION"])
                pos = (np.c_[pos, np.ones(len(pos))] @ world.T)[:, :3]
                if "indices" in prim:
                    idx = _accessor(gltf, binary, prim["indices"]).astype(np.int64).reshape(-1, 3)
                else:
                    idx = np.arange(len(pos)).reshape(-1, 3)
                mat = gltf.get("materials", [{}])[prim["material"]] if "material" in prim else {}
                base = np.array(mat.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0.8, 0.8, 0.8, 1]))
                col = np.tile(base, (len(pos), 1))
                sampler = _texture_sampler(gltf, binary, mat)
                if sampler and "TEXCOORD_0" in prim["attributes"]:
                    col = col * sampler(_accessor(gltf, binary, prim["attributes"]["TEXCOORD_0"]))
                if "COLOR_0" in prim["attributes"]:
                    vc = _accessor(gltf, binary, prim["attributes"]["COLOR_0"])
                    if vc.shape[1] == 3:
                        vc = np.c_[vc, np.ones(len(vc))]
                    col = col * vc
                if np.linalg.det(world[:3, :3]) < 0:
                    idx = idx[:, ::-1]
                verts.append(pos)
                faces.append(idx + offset)
                colors.append(col)
                offset += len(pos)
        for child in node.get("children", []):
            visit(child, world)

    scene = gltf.get("scenes", [{}])[gltf.get("scene", 0)] if gltf.get("scenes") else {"nodes": list(range(len(gltf["nodes"])))}
    for root in scene.get("nodes", []):
        visit(root, np.eye(4))
    if not verts:
        raise ValueError("In der Datei ist kein 3D-Netz.")
    return {"vertices": np.concatenate(verts), "faces": np.concatenate(faces),
            "colors": np.clip(np.concatenate(colors), 0, 1),
            "animations": [a.get("name", f"Animation {i + 1}") for i, a in enumerate(gltf.get("animations", []))]}


def orient(mesh, turns=0):
    """Figur um die Hochachse drehen (Vierteldrehungen), auf den Boden stellen und mittig ausrichten."""
    v = mesh["vertices"] @ rot_y(math.radians(90 * turns)).T
    lo, hi = v.min(0), v.max(0)
    v = v - [(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]
    out = dict(mesh)
    out["vertices"] = v
    return out


def normals(vertices, faces):
    n = np.zeros_like(vertices)
    tri = vertices[faces]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    for i in range(3):
        np.add.at(n, faces[:, i], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def simplify(vertices, faces, colors, target=5000):
    """Grobe Vereinfachung (Raster-Zusammenfassung) – nur für die Vorschau."""
    if len(faces) <= target:
        return vertices, faces, colors
    size = (vertices.max(0) - vertices.min(0)).max()
    cells = int(max(8, math.sqrt(target) * 1.4))
    for _ in range(6):
        key = np.floor((vertices - vertices.min(0)) / (size / cells)).astype(np.int64)
        _uniq, inverse = np.unique(key, axis=0, return_inverse=True)
        inverse = inverse.reshape(-1)
        f = inverse[faces]
        keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
        f = np.unique(np.sort(f[keep], axis=1), axis=0) if keep.any() else f[:1]
        if len(f) <= target * 1.3 or cells <= 8:
            break
        cells = int(cells * 0.8)
    count = inverse.max() + 1
    nv = np.zeros((count, 3))
    nc = np.zeros((count, colors.shape[1]))
    n = np.zeros(count)
    np.add.at(nv, inverse, vertices)
    np.add.at(nc, inverse, colors)
    np.add.at(n, inverse, 1)
    # Ausrichtung der Dreiecke nach dem Original
    keep_faces = inverse[faces]
    ok = (keep_faces[:, 0] != keep_faces[:, 1]) & (keep_faces[:, 1] != keep_faces[:, 2]) & (keep_faces[:, 0] != keep_faces[:, 2])
    f = keep_faces[ok]
    _u, first = np.unique(np.sort(f, axis=1), axis=0, return_index=True)
    return nv / n[:, None], f[np.sort(first)], nc / n[:, None]


# ---- Skelett ------------------------------------------------------------------------------

def fit(vertices):
    return {k: np.asarray(v, float) for k, v in R.fit_template(vertices).items()}


def base_pose(joints):
    """Grundhaltung: Arme hängen locker (ca. 12° vom Körper weg), egal ob T- oder A-Pose."""
    base = {}
    for arm, fore, sign in (("LeftArm", "LeftForeArm", 1), ("RightArm", "RightForeArm", -1)):
        rest = joints[fore] - joints[arm]
        target = np.array([sign * math.sin(math.radians(12)), -math.cos(math.radians(12)), 0.0])
        base[arm] = between(rest, target)
    return base


def pose_matrices(joints, rotations, base=None, hips_offset=0.0):
    """Gelenk-Weltmatrizen (3×3, Position) für die Haltung rotations {Gelenk: 3×3 lokal}."""
    base = base or {}
    world_r, world_t = {}, {}
    for name in ORDER:
        local = rotations.get(name, np.eye(3))
        if name in base:
            local = local @ base[name]
        parent = PARENT[name]
        if parent is None:
            world_r[name] = local
            world_t[name] = joints[name] + np.array([0.0, hips_offset, 0.0])
        else:
            world_r[name] = world_r[parent] @ local
            world_t[name] = world_t[parent] + world_r[parent] @ (joints[name] - joints[parent])
    return world_r, world_t


def skin(vertices, joints, weights, world_r, world_t):
    jidx, w = weights
    out = np.zeros_like(vertices)
    for i, name in enumerate(NAMES):
        mask = (jidx == i)
        wv = (w * mask).sum(1)
        sel = wv > 0
        if not sel.any():
            continue
        moved = (vertices[sel] - joints[name]) @ world_r[name].T + world_t[name]
        out[sel] += moved * wv[sel, None]
    return out


# ---- Bewegungen ----------------------------------------------------------------------------

def sample(anim, t):
    """Haltung zum Zeitpunkt t: ({Gelenk: (x, y, z) Grad}, Hüfthöhe-Versatz als Anteil der Körpergröße)."""
    length = max(0.05, float(anim.get("length", 1.0)))
    if anim.get("loop", True):
        t = t % length
    else:
        t = min(max(t, 0.0), length)
    out = {}
    for joint, keys in anim.get("tracks", {}).items():
        out[joint] = _interp(keys, t, length, anim.get("loop", True), 3)
    bob = anim.get("bob") or []
    dy = _interp(bob, t, length, anim.get("loop", True), 1)[0] if bob else 0.0
    return out, dy


def _interp(keys, t, length, loop, width):
    keys = sorted(keys, key=lambda k: k[0])
    if not keys:
        return [0.0] * width
    if len(keys) == 1:
        return list(keys[0][1:1 + width])
    if t <= keys[0][0]:
        if loop:
            a, b = keys[-1], keys[0]
            span = (length - a[0]) + b[0]
            f = ((t + length - a[0]) / span) if span > 1e-6 else 0
            return [a[1 + i] + (b[1 + i] - a[1 + i]) * f for i in range(width)]
        return list(keys[0][1:1 + width])
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            span = b[0] - a[0]
            f = (t - a[0]) / span if span > 1e-6 else 0
            f = f * f * (3 - 2 * f)  # weich ein- und ausschwingen
            return [a[1 + i] + (b[1 + i] - a[1 + i]) * f for i in range(width)]
    a = keys[-1]
    if loop:
        b = keys[0]
        span = (length - a[0]) + b[0]
        f = (t - a[0]) / span if span > 1e-6 else 0
        return [a[1 + i] + (b[1 + i] - a[1 + i]) * f for i in range(width)]
    return list(a[1:1 + width])


def rotations_at(anim, t):
    angles, dy = sample(anim, t)
    return {j: euler(a) for j, a in angles.items() if j in INDEX}, dy


def preset(kind, tempo=1.0, stride=28.0, arms=24.0, waddle=0.0, flap=0.0, bounce=1.0, lean=0.0):
    """Fertige Bewegung aus Reglern. kind: idle, walk, run, jump, fall, cheer, hit."""
    tracks = {}
    bob = []

    def key(joint, t, x=0.0, y=0.0, z=0.0):
        tracks.setdefault(joint, []).append([round(t, 4), round(x, 2), round(y, 2), round(z, 2)])

    if kind in ("walk", "run"):
        run = kind == "run"
        period = (0.7 if run else 1.1) / max(0.2, tempo)
        s = stride * (1.4 if run else 1.0)
        a = arms * (1.5 if run else 1.0)
        knee = s * (1.9 if run else 1.4)
        steps = 12
        for i in range(steps):
            t = period * i / steps
            ph = 2 * math.pi * i / steps
            left = -s * math.sin(ph)
            right = s * math.sin(ph)
            key("LeftUpLeg", t, left - (6 if run else 0), 0, -waddle * 0.3 * math.sin(ph))
            key("RightUpLeg", t, right - (6 if run else 0), 0, -waddle * 0.3 * math.sin(ph))
            key("LeftLeg", t, knee * max(0.0, math.cos(ph)) + (8 if run else 2))
            key("RightLeg", t, knee * max(0.0, -math.cos(ph)) + (8 if run else 2))
            key("LeftFoot", t, -left * 0.4)
            key("RightFoot", t, -right * 0.4)
            flap_out = flap * (0.5 + 0.5 * math.sin(2 * ph))
            key("LeftArm", t, a * math.sin(ph), 0, flap_out)
            key("RightArm", t, -a * math.sin(ph), 0, -flap_out)
            key("LeftForeArm", t, -(30 if run else 12) - flap * 0.3 * math.sin(2 * ph))
            key("RightForeArm", t, -(30 if run else 12) + flap * 0.3 * math.sin(2 * ph))
            key("Hips", t, (8 if run else 0) + lean, waddle * 0.4 * math.sin(ph), waddle * math.sin(ph))
            key("Spine", t, lean * 0.5, -a * 0.15 * math.sin(ph), -waddle * 0.6 * math.sin(ph))
            key("Spine2", t, (6 if run else 0), -a * 0.1 * math.sin(ph), -waddle * 0.3 * math.sin(ph))
            key("Head", t, -(4 if run else 0), 0, waddle * 0.3 * math.sin(ph))
            bob.append([round(t, 4), round(bounce * (0.022 if run else 0.012) * math.cos(2 * ph), 4)])
        return {"length": period, "loop": True, "tracks": tracks, "bob": bob}
    if kind == "idle":
        period = 3.0 / max(0.2, tempo)
        for i in range(6):
            t = period * i / 6
            ph = 2 * math.pi * i / 6
            key("Spine1", t, 1.5 * math.sin(ph))
            key("Spine2", t, 1.5 * math.sin(ph))
            key("LeftArm", t, 0, 0, 2 + 1.5 * math.sin(ph) + flap * 0.2)
            key("RightArm", t, 0, 0, -2 - 1.5 * math.sin(ph) - flap * 0.2)
            key("LeftForeArm", t, -8)
            key("RightForeArm", t, -8)
            key("Head", t, 2 * math.sin(ph + 1), 3 * math.sin(ph * 0.5), 0)
            key("Hips", t, 0, 0, waddle * 0.3 * math.sin(ph))
            bob.append([round(t, 4), round(bounce * 0.004 * math.sin(ph), 4)])
        return {"length": period, "loop": True, "tracks": tracks, "bob": bob}
    if kind == "jump":
        for t, leg, knee, arm, dy in ((0.0, -10, 20, -20, 0.0), (0.12, -35, 60, -150, 0.0),
                                      (0.45, -45, 80, -160, 0.0), (0.7, -20, 30, -60, 0.0)):
            key("LeftUpLeg", t, leg)
            key("RightUpLeg", t, leg * 0.6)
            key("LeftLeg", t, knee)
            key("RightLeg", t, knee * 0.8)
            key("LeftArm", t, arm * arms / 24, 0, 10 + flap)
            key("RightArm", t, arm * arms / 24 * 0.9, 0, -10 - flap)
            key("Spine", t, 5)
            bob.append([t, dy])
        return {"length": 0.7 / max(0.2, tempo), "loop": False, "tracks": _scale_time(tracks, 1 / max(0.2, tempo)),
                "bob": bob}
    if kind == "fall":
        period = 0.6 / max(0.2, tempo)
        for i in range(6):
            t = period * i / 6
            ph = 2 * math.pi * i / 6
            key("LeftArm", t, -20, 0, 70 + 25 * math.sin(ph) + flap)
            key("RightArm", t, -20, 0, -70 - 25 * math.sin(ph) - flap)
            key("LeftUpLeg", t, -20 + 10 * math.sin(ph))
            key("RightUpLeg", t, -10 - 10 * math.sin(ph))
            key("LeftLeg", t, 30)
            key("RightLeg", t, 40)
            key("Head", t, -10)
        return {"length": period, "loop": True, "tracks": tracks, "bob": []}
    if kind == "cheer":
        period = 0.8 / max(0.2, tempo)
        for i in range(8):
            t = period * i / 8
            ph = 2 * math.pi * i / 8
            key("LeftArm", t, -10, 0, 150 + 15 * math.sin(ph))
            key("RightArm", t, -10, 0, -150 - 15 * math.sin(ph))
            key("LeftForeArm", t, 0, 0, 10 * math.sin(ph))
            key("RightForeArm", t, 0, 0, -10 * math.sin(ph))
            key("Head", t, -12, 0, 6 * math.sin(ph))
            key("LeftUpLeg", t, -8 * max(0, math.sin(ph)))
            key("LeftLeg", t, 14 * max(0, math.sin(ph)))
            key("RightUpLeg", t, -8 * max(0, math.sin(ph)))
            key("RightLeg", t, 14 * max(0, math.sin(ph)))
            bob.append([round(t, 4), round(bounce * 0.05 * max(0.0, math.sin(ph)), 4)])
        return {"length": period, "loop": True, "tracks": tracks, "bob": bob}
    if kind.startswith("attack"):
        style = {"attack1": "punch", "attack2": "kick", "attack3": "swing", "attack4": "spin"}.get(kind, "punch")
        f = 1 / max(0.2, tempo)
        if style == "punch":   # rechter Arm stößt nach vorn
            for t, arm, fore, spine, hips in ((0.0, 0, -10, 0, 0), (0.08, 20, -70, -5, -10),
                                               (0.18, -85, -5, 10, 20), (0.32, -80, -10, 8, 15), (0.5, 0, -10, 0, 0)):
                key("RightArm", t * f, arm * arms / 24, 0, -8)
                key("RightForeArm", t * f, fore)
                key("Spine", t * f, spine * 0.5, hips)
                key("Hips", t * f, 0, hips * 0.5)
                key("LeftArm", t * f, -20, 0, 10)
                key("LeftForeArm", t * f, -60)
        elif style == "kick":   # rechtes Bein tritt nach vorn
            for t, leg, knee, lean in ((0.0, 0, 0, 0), (0.12, -40, 80, -5), (0.24, -85, 5, -12),
                                       (0.38, -80, 10, -10), (0.55, 0, 0, 0)):
                key("RightUpLeg", t * f, leg * stride / 28)
                key("RightLeg", t * f, knee)
                key("Spine", t * f, lean)
                key("LeftArm", t * f, -lean, 0, 35)
                key("RightArm", t * f, lean, 0, -35)
        elif style == "swing":   # beide Arme schlagen von oben nach unten
            for t, arm, spine in ((0.0, 0, 0), (0.15, -170, -12), (0.3, -40, 20), (0.45, -30, 15), (0.65, 0, 0)):
                key("LeftArm", t * f, arm * arms / 24, 0, 8)
                key("RightArm", t * f, arm * arms / 24, 0, -8)
                key("LeftForeArm", t * f, -20)
                key("RightForeArm", t * f, -20)
                key("Spine", t * f, spine)
                key("Spine2", t * f, spine * 0.5)
        else:   # Wirbel: einmal um die eigene Achse, Arme ausgestreckt
            for i in range(9):
                t = 0.6 * i / 8
                key("Hips", t * f, 0, 360 * i / 8)
                key("LeftArm", t * f, 0, 0, 85)
                key("RightArm", t * f, 0, 0, -85)
        return {"length": round(max(k[0] for keys in tracks.values() for k in keys), 3), "loop": False,
                "tracks": tracks, "bob": bob}
    if kind == "hit":
        for t, spine, head, arm in ((0.0, 0, 0, 0), (0.1, -18, -20, 40), (0.5, 0, 0, 0)):
            key("Spine", t, spine)
            key("Spine2", t, spine * 0.6)
            key("Head", t, head)
            key("LeftArm", t, -arm * 0.6, 0, arm)
            key("RightArm", t, -arm * 0.6, 0, -arm)
        return {"length": 0.5, "loop": False, "tracks": tracks, "bob": []}
    raise ValueError(kind)


def _scale_time(tracks, f):
    return {j: [[k[0] * f] + k[1:] for k in keys] for j, keys in tracks.items()}


# ---- KI ---------------------------------------------------------------------------------------

def ai_prompt(description, slot, joints):
    """Auftrag für Claude: Bewegung als JSON mit Schlüsselbildern."""
    height = float(joints["HeadTop_End"][1] - min(joints["LeftToeBase"][1], joints["RightToeBase"][1]))
    names = ", ".join(f"{n} ({LABEL[n]})" for n in NAMES if not n.endswith("_End"))
    return f"""Du entwirfst eine Bewegung (Animation) für eine Spielfigur eines 3D-Jump'n'Runs.
Wunsch des Nutzers für die Bewegung „{SLOT_NAME.get(slot, slot)}“: {description}

Skelett (Mixamo-Namen): {names}.
Die Figur ist {height:.2f} m groß, steht aufrecht, schaut nach +Z, ihre linke Seite liegt bei +X.
Grundhaltung (alle Winkel 0): aufrecht, Beine gerade, Arme hängen locker neben dem Körper.
Winkel in Grad je Gelenk als [x, y, z], relativ zur Grundhaltung, Drehreihenfolge X, dann Y, dann Z:
- x positiv: Oberkörper/Kopf neigt sich nach vorn; ein hängender Arm oder ein Bein schwingt nach HINTEN.
- x negativ: Arm/Bein schwingt nach VORN. Knie (LeftLeg/RightLeg): positiv = Unterschenkel beugt nach hinten (natürlich).
  Ellbogen (LeftForeArm/RightForeArm): negativ = Unterarm hebt sich nach vorn (natürlich).
- z: seitlich. LeftArm z positiv hebt den linken Arm seitlich nach außen/oben (90 = waagerecht, 170 = über dem Kopf);
  RightArm genau umgekehrt (negativ). Hips z kippt die Hüfte zur Seite (Watscheln).
- y: Drehung um die Hochachse (Hüfte, Oberkörper, Kopf).
Kindgelenke drehen sich mit ihren Eltern mit. Die Figur bleibt am Ort (das Spiel bewegt sie vorwärts).
Bewegungen sollen ausdrucksstark und lesbar sein, aber anatomisch möglich (Knie nie negativ).

Antworte NUR mit JSON, ohne Erklärung, in genau diesem Format:
{{"name": "kurzer deutscher Name", "length": Sekunden pro Durchlauf (0.4–4), "loop": true/false,
  "keys": [{{"t": 0.0, "bob": 0.0, "Hips": [0,0,0], "LeftUpLeg": [-25,0,0], ...}}, ...]}}
- 6 bis 16 Schlüsselbilder, t von 0 bis unter length; bei loop=true soll der Anfang nahtlos an das Ende passen.
- "bob" = Hüfte hoch/runter als Anteil der Körpergröße (z. B. 0.02), optional.
- Nur Gelenke aufführen, die sich bewegen; fehlt ein Gelenk in einem Schlüsselbild, wird dazwischen weich übergeblendet.
"""


def parse_ai(text):
    """Antwort von Claude → Bewegung (dict) oder ValueError."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("Die KI hat keine Bewegung geliefert.")
    raw = match.group(0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
    length = min(4.0, max(0.3, float(data.get("length", 1.0))))
    tracks, bob = {}, []
    for k in data.get("keys", []):
        t = min(length, max(0.0, float(k.get("t", 0))))
        for joint, value in k.items():
            if joint in INDEX and isinstance(value, (list, tuple)) and len(value) == 3:
                ang = [max(-175.0, min(175.0, float(v))) for v in value]
                if joint in ("LeftLeg", "RightLeg"):
                    ang[0] = max(-5.0, ang[0])
                tracks.setdefault(joint, []).append([round(t, 4)] + [round(a, 2) for a in ang])
        if "bob" in k:
            bob.append([round(t, 4), max(-0.3, min(0.3, float(k["bob"])))])
    if not tracks:
        raise ValueError("Die KI-Bewegung enthält keine Gelenke.")
    return {"name": str(data.get("name", "KI-Bewegung"))[:40], "length": length,
            "loop": bool(data.get("loop", True)), "tracks": tracks, "bob": bob}


# ---- Speichern ------------------------------------------------------------------------------

def export(path, mesh, joints, animations):
    """Animierte GLB schreiben. animations = {Name: Bewegung}; Namen sind die festen Plätze (idle, walk, …)."""
    v = np.asarray(mesh["vertices"], np.float32)
    f = np.asarray(mesh["faces"], np.uint32)
    c = np.asarray(mesh["colors"])
    n = normals(np.asarray(v, float), f.astype(np.int64))
    base = base_pose(joints)
    height = float(joints["HeadTop_End"][1])
    baked = {}
    for name, anim in animations.items():
        length = max(0.05, float(anim.get("length", 1.0)))
        frames = max(2, int(round(length * FPS)) + 1)
        times = np.linspace(0, length, frames)
        rot = {j: [] for j in NAMES}
        trans = []
        for t in times:
            rots, dy = rotations_at(anim, t if t < length or not anim.get("loop", True) else 0.0)
            for j in NAMES:
                local = rots.get(j, np.eye(3))
                if j in base:
                    local = local @ base[j]
                rot[j].append(quat(local))
            trans.append(joints["Hips"] + [0, dy * height, 0])
        tracks = {j: (times, np.array(q)) for j, q in rot.items()
                  if not np.allclose(np.array(q), [0, 0, 0, 1], atol=1e-5)}
        baked[name] = {"rotation": tracks, "translation": {"Hips": (times, np.array(trans))}}
    _write(path, v, f, c, n, joints, baked)
    return path


def _write(path, v, f, colors, nrm, joints, animations):
    b = R._Bin()
    attributes = {"POSITION": b.add(v, R.FLOAT, "VEC3", R.ARRAY, minmax=True),
                  "NORMAL": b.add(np.asarray(nrm, np.float32), R.FLOAT, "VEC3", R.ARRAY)}
    col = np.clip(np.asarray(colors, float) * 255, 0, 255).astype(np.uint8)
    if col.shape[1] == 3:
        col = np.c_[col, np.full(len(col), 255, np.uint8)]
    attributes["COLOR_0"] = b.add(col, R.UBYTE, "VEC4", R.ARRAY, normalized=True)
    jidx, weights = R.skin_weights(np.asarray(v, float), joints)
    attributes["JOINTS_0"] = b.add(np.asarray(jidx, np.uint16), R.USHORT, "VEC4", R.ARRAY)
    attributes["WEIGHTS_0"] = b.add(np.asarray(weights, np.float32), R.FLOAT, "VEC4", R.ARRAY)
    first = 1
    nodes = [{"name": "Figur", "mesh": 0, "skin": 0}]
    for name in NAMES:
        local = joints[name] - joints[PARENT[name]] if PARENT[name] else joints[name]
        node = {"name": PREFIX + name, "translation": [float(x) for x in local]}
        if CHILDREN[name]:
            node["children"] = [first + INDEX[c] for c in CHILDREN[name]]
        nodes.append(node)
    ibm = np.zeros((len(NAMES), 16), np.float32)
    for i, name in enumerate(NAMES):
        m = np.eye(4, dtype=np.float32)
        m[:3, 3] = -joints[name]
        ibm[i] = m.T.reshape(-1)
    gltf = {"asset": {"version": "2.0", "generator": "Creative Engine"}, "scene": 0,
            "scenes": [{"nodes": [0, first + INDEX["Hips"]]}], "nodes": nodes,
            "materials": [{"name": "Figur", "pbrMetallicRoughness": {
                "baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0.0, "roughnessFactor": 0.85}}],
            "skins": [{"name": "Skelett", "skeleton": first + INDEX["Hips"],
                       "joints": [first + i for i in range(len(NAMES))],
                       "inverseBindMatrices": b.add(ibm, R.FLOAT, "MAT4")}]}
    if animations:
        gltf["animations"] = []
        for anim_name, parts in animations.items():
            samplers, channels = [], []
            for path_kind, tracks in (("rotation", parts["rotation"]), ("translation", parts["translation"])):
                for joint, (times, values) in tracks.items():
                    ti = b.add(np.asarray(times, np.float32), R.FLOAT, "SCALAR", minmax=True)
                    vo = b.add(np.asarray(values, np.float32), R.FLOAT, "VEC4" if path_kind == "rotation" else "VEC3")
                    samplers.append({"input": ti, "output": vo, "interpolation": "LINEAR"})
                    channels.append({"sampler": len(samplers) - 1,
                                     "target": {"node": first + INDEX[joint], "path": path_kind}})
            gltf["animations"].append({"name": anim_name, "samplers": samplers, "channels": channels})
    indices = b.add(np.asarray(f, np.uint32).reshape(-1), R.UINT, "SCALAR", R.ELEMENTS)
    gltf["meshes"] = [{"name": "Figur", "primitives": [{"attributes": attributes, "indices": indices, "material": 0}]}]
    gltf["bufferViews"] = b.views
    gltf["accessors"] = b.accessors
    while len(b.data) % 4:
        b.data.append(0)
    gltf["buffers"] = [{"byteLength": len(b.data)}]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(b.data)
    with open(path, "wb") as out:
        out.write(struct.pack("<III", 0x46546C67, 2, total))
        out.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        out.write(struct.pack("<II", len(b.data), 0x004E4942) + bytes(b.data))
    return path


# ---- Beispielfigur ----------------------------------------------------------------------------

def _limb(a, b, w, d, color, segments=6):
    """Quader von a nach b (unterteilt, damit er sich biegen kann)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    axis = b - a
    length = np.linalg.norm(axis)
    u = axis / length
    side = np.cross(u, [0, 0, 1]) if abs(u[2]) < 0.9 else np.cross(u, [1, 0, 0])
    side /= np.linalg.norm(side)
    up = np.cross(side, u)
    ring = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    verts, faces = [], []
    for i in range(segments + 1):
        c = a + axis * i / segments
        for sx, sy in ring:
            verts.append(c + side * sx * w / 2 + up * sy * d / 2)
    for i in range(segments):
        for k in range(4):
            p0, p1 = i * 4 + k, i * 4 + (k + 1) % 4
            q0, q1 = p0 + 4, p1 + 4
            faces += [[p0, p1, q1], [p0, q1, q0]]
    last = segments * 4
    faces += [[0, 2, 1], [0, 3, 2], [last, last + 1, last + 2], [last, last + 2, last + 3]]
    colors = np.tile(np.asarray(color, float), (len(verts), 1))
    return np.array(verts), np.array(faces), colors


def demo_figure():
    """Einfache Klötzchen-Figur in T-Pose (1,7 m) – zum Ausprobieren ohne eigenes Modell."""
    skin_c, shirt, pants, shoe, hair = (0.96, 0.78, 0.64, 1), (0.24, 0.44, 0.88, 1), (0.2, 0.22, 0.3, 1), \
        (0.95, 0.42, 0.3, 1), (0.35, 0.22, 0.12, 1)
    parts = [
        _limb([0, 0.9, 0], [0, 1.42, 0], 0.4, 0.24, shirt, 8),             # Rumpf
        _limb([0, 1.42, 0], [0, 1.5, 0], 0.12, 0.12, skin_c, 2),           # Hals
        _limb([0, 1.5, 0.01], [0, 1.72, 0.01], 0.26, 0.26, skin_c, 4),     # Kopf
        _limb([0, 1.66, -0.01], [0, 1.75, -0.01], 0.28, 0.28, hair, 1),    # Haare
        _limb([0.2, 1.38, 0], [0.82, 1.38, 0], 0.11, 0.11, shirt, 10),     # linker Arm
        _limb([-0.2, 1.38, 0], [-0.82, 1.38, 0], 0.11, 0.11, shirt, 10),   # rechter Arm
        _limb([0.82, 1.38, 0], [0.92, 1.38, 0], 0.1, 0.1, skin_c, 2),
        _limb([-0.82, 1.38, 0], [-0.92, 1.38, 0], 0.1, 0.1, skin_c, 2),
        _limb([0.1, 0.92, 0], [0.1, 0.08, 0], 0.15, 0.16, pants, 10),      # linkes Bein
        _limb([-0.1, 0.92, 0], [-0.1, 0.08, 0], 0.15, 0.16, pants, 10),
        _limb([0.1, 0.08, -0.03], [0.1, 0.0, -0.03], 0.15, 0.26, shoe, 1),
        _limb([-0.1, 0.08, -0.03], [-0.1, 0.0, -0.03], 0.15, 0.26, shoe, 1),
        _limb([0.06, 1.62, 0.13], [0.06, 1.58, 0.13], 0.04, 0.02, (0.1, 0.1, 0.15, 1), 1),   # Augen
        _limb([-0.06, 1.62, 0.13], [-0.06, 1.58, 0.13], 0.04, 0.02, (0.1, 0.1, 0.15, 1), 1),
    ]
    verts, faces, colors, off = [], [], [], 0
    for v, f, c in parts:
        verts.append(v)
        faces.append(f + off)
        colors.append(c)
        off += len(v)
    return {"vertices": np.concatenate(verts), "faces": np.concatenate(faces), "colors": np.concatenate(colors),
            "animations": []}


def demo_glb(path):
    """Beispielfigur als (unanimierte) GLB-Datei speichern."""
    m = demo_figure()
    R.write_glb(path, m["vertices"], m["faces"], m["colors"], normals(m["vertices"], m["faces"]))
    return path
