"""Kleine Beispiel-Figur als GLB (Creative-Rakete aus Zylindern und Kegeln) – für Prüfungen der 3D-Ansicht.
   python3 tools/glb-beispiel.py ausgabe.glb"""
import json
import math
import struct
import sys


def lathe(profile, segments=48):
    """Drehkörper aus (radius, höhe)-Punkten → Eckpunkte, Normalen, Dreiecke."""
    verts, norms, idx = [], [], []
    rings = len(profile)
    for i, (r, y) in enumerate(profile):
        # Normale grob aus den Nachbarpunkten
        r0, y0 = profile[max(0, i - 1)]
        r1, y1 = profile[min(rings - 1, i + 1)]
        dr, dy = r1 - r0, y1 - y0
        nx, ny = dy, -dr
        ln = math.hypot(nx, ny) or 1
        nx, ny = nx / ln, ny / ln
        for s in range(segments + 1):
            a = 2 * math.pi * s / segments
            verts.append((r * math.cos(a), y, r * math.sin(a)))
            norms.append((nx * math.cos(a), ny, nx * math.sin(a)))
    for i in range(rings - 1):
        for s in range(segments):
            a = i * (segments + 1) + s
            b = a + segments + 1
            idx += [a, b, a + 1, a + 1, b, b + 1]
    return verts, norms, idx


def fin(angle):
    """Flosse als dünne Platte (zwei Seiten)."""
    pts = [(0.17, 0.05), (0.42, -0.08), (0.42, 0.12), (0.17, 0.45)]
    c, s = math.cos(angle), math.sin(angle)
    verts, norms, idx = [], [], []
    for side in (1, -1):
        base = len(verts)
        for r, y in pts:
            off = 0.012 * side
            x, z = r * c - off * s, r * s + off * c
            verts.append((x, y, z))
            norms.append((-s * side, 0, c * side))
        idx += [base, base + 1, base + 2, base, base + 2, base + 3] if side == 1 else \
               [base, base + 2, base + 1, base, base + 3, base + 2]
    return verts, norms, idx


def main(out):
    body = lathe([(0.0, 0.0), (0.16, 0.02), (0.19, 0.25), (0.2, 0.7), (0.17, 1.0), (0.0, 1.0)])
    nose = lathe([(0.17, 1.0), (0.15, 1.12), (0.1, 1.25), (0.0, 1.36)])
    window = lathe([(0.0, 0.75), (0.07, 0.755), (0.075, 0.76)], 32)
    window = ([(x * 1.0, y, z + 0.0) for x, y, z in window[0]], window[1], window[2])
    # Fenster nach vorn auf die Hülle legen: Kreis in der x/y-Ebene bei z = 0.2
    win_v, win_n, win_i = [], [], []
    segs = 32
    win_v.append((0, 0.72, 0.205)); win_n.append((0, 0, 1))
    for s in range(segs + 1):
        a = 2 * math.pi * s / segs
        win_v.append((0.075 * math.cos(a), 0.72 + 0.075 * math.sin(a), 0.2))
        win_n.append((0, 0, 1))
    for s in range(1, segs + 1):
        win_i += [0, s, s + 1]
    flame = lathe([(0.0, 0.0), (0.12, -0.02), (0.08, -0.16), (0.0, -0.3)])
    fins = [fin(a) for a in (0.0, 2 * math.pi / 3, 4 * math.pi / 3)]
    fv, fn, fi = [], [], []
    for v, n, i in fins:
        base = len(fv)
        fv += v; fn += n; fi += [base + k for k in i]
    parts = [(body, (0.86, 0.9, 1.0, 1.0)), (nose, (0.56, 0.70, 1.0, 1.0)),
             ((win_v, win_n, win_i), (0.07, 0.08, 0.11, 1.0)), (flame, (1.0, 0.69, 0.48, 1.0)),
             ((fv, fn, fi), (1.0, 0.69, 0.48, 1.0))]

    blob = bytearray()
    views, accessors, prims, materials = [], [], [], []
    for (verts, norms, idx), color in parts:
        def add(data, target):
            while len(blob) % 4:
                blob.append(0)
            views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
            blob.extend(data)
            return len(views) - 1
        pv = add(b"".join(struct.pack("<3f", *v) for v in verts), 34962)
        nv = add(b"".join(struct.pack("<3f", *n) for n in norms), 34962)
        iv = add(b"".join(struct.pack("<I", i) for i in idx), 34963)
        mins = [min(v[k] for v in verts) for k in range(3)]
        maxs = [max(v[k] for v in verts) for k in range(3)]
        accessors += [
            {"bufferView": pv, "componentType": 5126, "count": len(verts), "type": "VEC3", "min": mins, "max": maxs},
            {"bufferView": nv, "componentType": 5126, "count": len(norms), "type": "VEC3"},
            {"bufferView": iv, "componentType": 5125, "count": len(idx), "type": "SCALAR"},
        ]
        a = len(accessors)
        materials.append({"pbrMetallicRoughness": {"baseColorFactor": list(color), "metallicFactor": 0.1,
                                                   "roughnessFactor": 0.45}, "doubleSided": True})
        prims.append({"attributes": {"POSITION": a - 3, "NORMAL": a - 2}, "indices": a - 1,
                      "material": len(materials) - 1})
    while len(blob) % 4:
        blob.append(0)
    gltf = {"asset": {"version": "2.0", "generator": "Creative OS"}, "scene": 0,
            "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "Rakete"}],
            "meshes": [{"primitives": prims}], "materials": materials, "accessors": accessors,
            "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(out, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))
    print("GLB geschrieben:", out, total, "Bytes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "rakete.glb")
