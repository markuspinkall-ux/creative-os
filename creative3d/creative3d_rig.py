"""Creative 3D – Skelett für Figuren (nur numpy, läuft im System-Python).

- Vorlage: menschliches Skelett mit Mixamo-Namen („mixamorig:Hips“ …), die
  KI-Animationswerkzeuge und Engines kennen. Wird an die Größe der Figur angepasst.
- Gewichtung: jeder Punkt der Oberfläche folgt den (bis zu) 4 nächsten Knochen,
  Arme/Beine der anderen Körperseite werden gemieden.
- Export: GLB 2.0 mit Netz, Farben, Skin und optional einer kurzen Probe-Bewegung.

Koordinaten wie im Export von Creative 3D: Y oben, die Figur schaut nach +Z,
ihre linke Seite liegt bei +X.
"""

import json
import math
import struct

import numpy as np

PREFIX = "mixamorig:"

# Name, Elternteil, Anzeigename
JOINTS = [
    ("Hips", None, "Hüfte"),
    ("Spine", "Hips", "Rücken unten"),
    ("Spine1", "Spine", "Rücken Mitte"),
    ("Spine2", "Spine1", "Brust"),
    ("Neck", "Spine2", "Hals"),
    ("Head", "Neck", "Kopf"),
    ("HeadTop_End", "Head", "Scheitel"),
    ("LeftShoulder", "Spine2", "Schlüsselbein links"),
    ("LeftArm", "LeftShoulder", "Schulter links"),
    ("LeftForeArm", "LeftArm", "Ellbogen links"),
    ("LeftHand", "LeftForeArm", "Hand links"),
    ("RightShoulder", "Spine2", "Schlüsselbein rechts"),
    ("RightArm", "RightShoulder", "Schulter rechts"),
    ("RightForeArm", "RightArm", "Ellbogen rechts"),
    ("RightHand", "RightForeArm", "Hand rechts"),
    ("LeftUpLeg", "Hips", "Hüftgelenk links"),
    ("LeftLeg", "LeftUpLeg", "Knie links"),
    ("LeftFoot", "LeftLeg", "Knöchel links"),
    ("LeftToeBase", "LeftFoot", "Zehen links"),
    ("RightUpLeg", "Hips", "Hüftgelenk rechts"),
    ("RightLeg", "RightUpLeg", "Knie rechts"),
    ("RightFoot", "RightLeg", "Knöchel rechts"),
    ("RightToeBase", "RightFoot", "Zehen rechts"),
]
NAMES = [j[0] for j in JOINTS]
PARENT = {j[0]: j[1] for j in JOINTS}
LABEL = {j[0]: j[2] for j in JOINTS}
INDEX = {name: i for i, name in enumerate(NAMES)}


def mirror_name(name):
    if name.startswith("Left"):
        return "Right" + name[4:]
    if name.startswith("Right"):
        return "Left" + name[5:]
    return None


def side(name):
    return 1 if name.startswith("Left") else -1 if name.startswith("Right") else 0


# ---- Vorlage einpassen -------------------------------------------------------------------

def fit_template(vertices):
    """Gelenke grob an die Figur anpassen → {Name: np.array([x, y, z])}.
    Proportionen eines Menschen relativ zur Höhe; ausgestreckte Arme (T-Pose)
    werden an der Breite der Figur erkannt."""
    v = np.asarray(vertices, dtype=np.float64)
    lo, hi = v.min(0), v.max(0)
    height = max(hi[1] - lo[1], 1e-6)
    cx, cz = float(np.median(v[:, 0])), float(np.median(v[:, 2]))
    half_width = max(hi[0] - cx, cx - lo[0])
    y = lambda f: lo[1] + f * height  # noqa: E731
    H = height
    j = {
        "Hips": (cx, y(0.52), cz), "Spine": (cx, y(0.59), cz), "Spine1": (cx, y(0.66), cz),
        "Spine2": (cx, y(0.73), cz), "Neck": (cx, y(0.83), cz), "Head": (cx, y(0.87), cz),
        "HeadTop_End": (cx, hi[1], cz),
    }
    t_pose = half_width > 0.33 * H
    for s, name in ((1, "Left"), (-1, "Right")):
        j[name + "Shoulder"] = (cx + s * 0.06 * H, y(0.80), cz)
        j[name + "Arm"] = (cx + s * 0.16 * H, y(0.80), cz)
        if t_pose:
            reach = max(half_width * 0.92, 0.30 * H)
            j[name + "ForeArm"] = (cx + s * (0.16 * H + (reach - 0.16 * H) * 0.5), y(0.80), cz)
            j[name + "Hand"] = (cx + s * reach, y(0.80), cz)
        else:
            j[name + "ForeArm"] = (cx + s * 0.19 * H, y(0.63), cz)
            j[name + "Hand"] = (cx + s * 0.21 * H, y(0.49), cz)
        j[name + "UpLeg"] = (cx + s * 0.09 * H, y(0.50), cz)
        j[name + "Leg"] = (cx + s * 0.09 * H, y(0.27), cz)
        j[name + "Foot"] = (cx + s * 0.09 * H, y(0.05), cz)
        j[name + "ToeBase"] = (cx + s * 0.09 * H, lo[1], cz + 0.07 * H)
    return {name: np.array(j[name], dtype=np.float64) for name in NAMES}


# ---- Haut-Gewichte ------------------------------------------------------------------------

def _segments(joints):
    """Ein Knochenstück je Gelenk mit Kindern (zum ersten/mittleren Kind), Blätter mit kurzem Fortsatz."""
    children = {n: [c for c in NAMES if PARENT[c] == n] for n in NAMES}
    segs = []
    for name in NAMES:
        a = joints[name]
        kids = children[name]
        if name == "Hips":
            b = joints["Spine"]
        elif name == "Spine2":
            b = joints["Neck"]
        elif kids:
            b = joints[kids[0]]
        else:
            parent = joints[PARENT[name]]
            d = a - parent
            b = a + d * 0.35
        segs.append((a, b))
    return segs


def _point_segment_distance(p, a, b):
    ab = b - a
    denom = float(ab @ ab)
    if denom < 1e-12:
        return np.linalg.norm(p - a, axis=1)
    t = np.clip(((p - a) @ ab) / denom, 0.0, 1.0)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def skin_weights(vertices, joints, influences=4):
    """→ (Gelenk-Indizes uint16 [N,4], Gewichte float32 [N,4], Summe je Zeile = 1)."""
    v = np.asarray(vertices, dtype=np.float64)
    center = joints["Hips"][0]
    height = max(joints["HeadTop_End"][1] - joints["LeftToeBase"][1], 1e-6)
    margin = 0.03 * height
    dist = np.empty((len(v), len(NAMES)))
    vside = np.where(v[:, 0] > center + margin, 1, np.where(v[:, 0] < center - margin, -1, 0))
    for i, (name, (a, b)) in enumerate(zip(NAMES, _segments(joints))):
        d = _point_segment_distance(v, a, b)
        s = side(name)
        if s:                                   # Glieder der anderen Körperseite meiden
            d = np.where(vside == -s, d * 4.0 + 0.1 * height, d)
        dist[:, i] = d
    k = min(influences, len(NAMES))
    idx = np.argsort(dist, axis=1)[:, :k]
    d = np.take_along_axis(dist, idx, axis=1)
    w = 1.0 / np.maximum(d, 1e-4 * height) ** 4
    w /= w.sum(axis=1, keepdims=True)
    w[w < 0.01] = 0.0                            # winzige Einflüsse weglassen
    w /= w.sum(axis=1, keepdims=True)
    return idx.astype(np.uint16), w.astype(np.float32)


# ---- GLB schreiben -------------------------------------------------------------------------

def _quat(axis, degrees):
    ax = np.asarray(axis, dtype=np.float64)
    ax = ax / np.linalg.norm(ax)
    h = math.radians(degrees) / 2
    return [*(ax * math.sin(h)), math.cos(h)]


def probe_animation():
    """Kurze Probe-Bewegung: linker Arm hebt sich und winkt, Kopf nickt."""
    t = [0.0, 0.6, 1.0, 1.4, 1.8, 2.4]
    return {
        "Winken": {
            "LeftArm": (t, [_quat([0, 0, 1], a) for a in (0, 75, 75, 75, 75, 0)]),
            "LeftForeArm": (t, [_quat([0, 0, 1], a) for a in (0, 40, 70, 40, 70, 0)]),
            "Head": (t, [_quat([1, 0, 0], a) for a in (0, 8, 0, 8, 0, 0)]),
        }
    }


class _Bin:
    def __init__(self):
        self.data = bytearray()
        self.views = []
        self.accessors = []

    def add(self, array, component, kind, target=None, normalized=False, minmax=False):
        array = np.ascontiguousarray(array)
        while len(self.data) % 4:
            self.data.append(0)
        view = {"buffer": 0, "byteOffset": len(self.data), "byteLength": array.nbytes}
        if target:
            view["target"] = target
        self.data += array.tobytes()
        self.views.append(view)
        acc = {"bufferView": len(self.views) - 1, "componentType": component,
               "count": int(array.shape[0]), "type": kind}
        if normalized:
            acc["normalized"] = True
        if minmax:
            flat = array.reshape(array.shape[0], -1)
            acc["min"] = [float(x) for x in flat.min(0)]
            acc["max"] = [float(x) for x in flat.max(0)]
        self.accessors.append(acc)
        return len(self.accessors) - 1


FLOAT, UBYTE, USHORT, UINT = 5126, 5121, 5123, 5125
ARRAY, ELEMENTS = 34962, 34963


def write_glb(path, vertices, faces, colors=None, normals=None, joints=None, animations=None):
    """GLB schreiben. joints = {Name: Position} oder None (dann ohne Skelett)."""
    v = np.asarray(vertices, dtype=np.float32)
    f = np.asarray(faces, dtype=np.uint32).reshape(-1)
    b = _Bin()
    attributes = {"POSITION": b.add(v, FLOAT, "VEC3", ARRAY, minmax=True)}
    if normals is not None:
        n = np.asarray(normals, dtype=np.float32)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        attributes["NORMAL"] = b.add(n, FLOAT, "VEC3", ARRAY)
    if colors is not None:
        c = np.asarray(colors)
        if c.dtype != np.uint8:
            c = np.clip(np.asarray(c, dtype=np.float64) * (255 if c.max() <= 1.0 else 1), 0, 255).astype(np.uint8)
        if c.shape[1] == 3:
            c = np.concatenate([c, np.full((len(c), 1), 255, np.uint8)], axis=1)
        attributes["COLOR_0"] = b.add(c, UBYTE, "VEC4", ARRAY, normalized=True)
    gltf = {"asset": {"version": "2.0", "generator": "Creative 3D"},
            "scene": 0, "scenes": [{"nodes": [0]}],
            "materials": [{"name": "Figur", "pbrMetallicRoughness": {
                "baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0.0, "roughnessFactor": 0.85}}],
            "nodes": [{"name": "Figur", "mesh": 0}]}
    if joints is not None:
        jidx, weights = skin_weights(v, joints)
        attributes["JOINTS_0"] = b.add(jidx, USHORT, "VEC4", ARRAY)
        attributes["WEIGHTS_0"] = b.add(weights, FLOAT, "VEC4", ARRAY)
        first = 1                                   # Gelenk-Knoten folgen nach dem Netz-Knoten
        children = {n: [c for c in NAMES if PARENT[c] == n] for n in NAMES}
        for name in NAMES:
            pos = joints[name]
            local = pos - joints[PARENT[name]] if PARENT[name] else pos
            node = {"name": PREFIX + name, "translation": [float(x) for x in local]}
            if children[name]:
                node["children"] = [first + INDEX[c] for c in children[name]]
            gltf["nodes"].append(node)
        ibm = np.zeros((len(NAMES), 16), dtype=np.float32)
        for i, name in enumerate(NAMES):
            m = np.eye(4, dtype=np.float32)
            m[:3, 3] = -joints[name]
            ibm[i] = m.T.reshape(-1)                 # glTF: Spalten zuerst
        gltf["skins"] = [{"name": "Skelett", "skeleton": first + INDEX["Hips"],
                          "joints": [first + i for i in range(len(NAMES))],
                          "inverseBindMatrices": b.add(ibm, FLOAT, "MAT4")}]
        gltf["nodes"][0]["skin"] = 0
        gltf["scenes"][0]["nodes"] = [0, first + INDEX["Hips"]]
        if animations:
            gltf["animations"] = []
            for anim_name, tracks in animations.items():
                samplers, channels = [], []
                for joint, (times, rotations) in tracks.items():
                    ti = b.add(np.asarray(times, np.float32), FLOAT, "SCALAR", minmax=True)
                    ro = b.add(np.asarray(rotations, np.float32), FLOAT, "VEC4")
                    samplers.append({"input": ti, "output": ro, "interpolation": "LINEAR"})
                    channels.append({"sampler": len(samplers) - 1,
                                     "target": {"node": first + INDEX[joint], "path": "rotation"}})
                gltf["animations"].append({"name": anim_name, "samplers": samplers, "channels": channels})
    indices = b.add(f, UINT, "SCALAR", ELEMENTS)
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


def read_glb(path):
    """GLB → (JSON, Binärdaten). Zum Prüfen."""
    with open(path, "rb") as f:
        data = f.read()
    magic, version, total = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or total != len(data):
        raise ValueError("kein gültiges GLB")
    jlen, jtype = struct.unpack_from("<II", data, 12)
    gltf = json.loads(data[20:20 + jlen])
    blen, btype = struct.unpack_from("<II", data, 20 + jlen)
    if jtype != 0x4E4F534A or btype != 0x004E4942:
        raise ValueError("falsche Chunks")
    return gltf, data[28 + jlen:28 + jlen + blen]
