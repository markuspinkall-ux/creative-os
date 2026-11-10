"""Ausweich-Vorschau für Creative 3D – zeichnet die Figur ohne Grafikkarte.

Wird benutzt, wenn die Web-Vorschau (WebGL) auf dem PC nicht läuft, z. B.
wenn die eingebaute Browser-Engine die Grafikkarte abschaltet. Die Figur wird
als dichte, beleuchtete Punktwolke mit Tiefenpuffer gezeichnet (numpy), das
ist schnell genug zum Drehen mit der Maus.
"""

import math

import numpy as np

DEFAULT_COLOR = np.array([184, 195, 222], np.float32)
LIGHT = np.array([-.35, .55, .76], np.float32)
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def rotation(yaw, pitch):
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], np.float32)
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], np.float32)
    return rx @ ry


def disk(radius):
    r = max(0, int(radius))
    return [(dx, dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dx * dx + dy * dy <= r * r + r]


class Mesh:
    def __init__(self, vertices, faces, normals=None, colors=None):
        v = np.asarray(vertices, np.float32)
        if not len(v):
            raise ValueError("Die Figur hat keine Punkte.")
        lo, hi = v.min(axis=0), v.max(axis=0)
        self.center = (lo + hi) / 2
        self.vertices = v - self.center
        self.radius = float(np.linalg.norm(self.vertices, axis=1).max()) or 1.0
        faces = np.asarray(faces, np.int64).reshape(-1, 3) if faces is not None and len(faces) else None
        if normals is None or len(normals) != len(v):
            normals = vertex_normals(self.vertices, faces)
        n = np.asarray(normals, np.float32)
        self.normals = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
        if colors is not None and len(colors) == len(v):
            self.colors = np.asarray(colors, np.float32)[:, :3]
        else:
            self.colors = np.broadcast_to(DEFAULT_COLOR, (len(v), 3)).copy()
        # mittlere Kantenlänge → wie groß ein Punkt gezeichnet werden muss, damit keine Lücken bleiben
        if faces is not None:
            sample = faces[:: max(1, len(faces) // 20000)]
            edges = np.linalg.norm(self.vertices[sample[:, 0]] - self.vertices[sample[:, 1]], axis=1)
            self.edge = float(np.median(edges)) if len(edges) else self.radius / 100
            self._densify(faces)
        else:
            self.edge = self.radius / max(10, math.sqrt(len(v)))

    def _densify(self, faces):
        """Grobe Netze: zusätzliche Punkte auf den Dreiecken, damit die Fläche geschlossen wirkt."""
        target = self.radius / 220
        k = int(math.ceil(self.edge / target))
        if k <= 1 or not len(faces):
            return
        k = min(k, max(1, int(math.sqrt(1_500_000 / max(1, len(faces))))))
        if k <= 1:
            return
        weights = [(i / k, j / k, 1 - (i + j) / k) for i in range(k + 1) for j in range(k + 1 - i)
                   if 0 < i + j < k or (i, j) == (0, 0) and False]
        weights = [w for w in weights if not (1 in w)]           # Ecken gibt es schon
        if not weights:
            return
        w = np.array(weights, np.float32)                        # (m, 3)
        a, b, c = faces[:, 0], faces[:, 1], faces[:, 2]

        def mix(arr):
            return (w[:, 0, None, None] * arr[a][None] + w[:, 1, None, None] * arr[b][None]
                    + w[:, 2, None, None] * arr[c][None]).reshape(-1, arr.shape[1])

        extra_n = mix(self.normals)
        extra_n /= np.maximum(np.linalg.norm(extra_n, axis=1, keepdims=True), 1e-6)
        self.vertices = np.concatenate([self.vertices, mix(self.vertices)])
        self.normals = np.concatenate([self.normals, extra_n])
        self.colors = np.concatenate([self.colors, mix(self.colors)])
        self.edge /= k

    def render(self, size=520, yaw=30.0, pitch=-12.0, zoom=1.0, fast=False):
        """Bild als RGBA-Array (size × size × 4)."""
        size = int(size)
        rot = rotation(yaw, pitch)
        p = self.vertices @ rot.T
        n = self.normals @ rot.T
        scale = size * .44 / self.radius * zoom
        x = p[:, 0] * scale + size / 2
        y = -p[:, 1] * scale + size / 2
        z = p[:, 2]
        # Keine Rückseiten-Auslese über Normalen (deren Richtung ist nicht immer verlässlich):
        # der Tiefenpuffer entscheidet, Normalen werden zur Kamera gedreht.
        n = n * np.where(n[:, 2:3] < 0, -1, 1)
        keep = np.ones(len(z), bool)
        if fast and len(z) > 90000:
            keep = (np.arange(len(z)) % (len(z) // 90000 + 1)) == 0
        x, y, z, n, colors = x[keep], y[keep], z[keep], n[keep], self.colors[keep]
        shade = np.clip(n @ LIGHT, 0, 1) * .72 + .28
        rim = np.clip(1 - n[:, 2], 0, 1) ** 3 * .25          # leichter Kantenschimmer
        rgb = np.clip(colors * shade[:, None] + 255 * rim[:, None] * .35, 0, 255).astype(np.uint8)
        radius = min(5, max(1, round(self.edge * scale * (.55 if fast else .75))))
        xi0, yi0 = np.round(x).astype(np.int64), np.round(y).astype(np.int64)
        xs, ys, zs, cs = [], [], [], []
        for dx, dy in disk(radius):
            xs.append(xi0 + dx)
            ys.append(yi0 + dy)
            zs.append(z)
            cs.append(np.arange(len(z)))
        xa, ya, za, ca = np.concatenate(xs), np.concatenate(ys), np.concatenate(zs), np.concatenate(cs)
        inside = (xa >= 0) & (xa < size) & (ya >= 0) & (ya < size)
        xa, ya, za, ca = xa[inside], ya[inside], za[inside], ca[inside]
        image = np.zeros((size, size, 4), np.uint8)
        if not len(xa):
            return image
        index = ya * size + xa
        order = np.lexsort((za, index))                       # je Pixel der vorderste Punkt zuletzt
        index_sorted = index[order]
        last = np.ones(len(order), bool)
        last[:-1] = index_sorted[1:] != index_sorted[:-1]
        chosen = order[last]
        flat = image.reshape(-1, 4)
        flat[index[chosen], :3] = rgb[ca[chosen]]
        flat[index[chosen], 3] = 255
        return image


def vertex_normals(vertices, faces):
    normals = np.zeros_like(vertices)
    if faces is None:
        normals[:, 2] = 1
        return normals
    a, b, c = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    face_n = np.cross(b - a, c - a)
    for i in range(3):
        np.add.at(normals, faces[:, i], face_n)
    return normals


def uv_sphere(rings=40, segments=60):
    """Testfigur."""
    verts, faces = [], []
    for i in range(rings + 1):
        t = math.pi * i / rings
        for j in range(segments):
            s = 2 * math.pi * j / segments
            verts.append((math.sin(t) * math.cos(s), math.cos(t), math.sin(t) * math.sin(s)))
    for i in range(rings):
        for j in range(segments):
            a, b = i * segments + j, i * segments + (j + 1) % segments
            c, d = a + segments, b + segments
            faces += [(a, c, b), (b, c, d)]
    return np.array(verts, np.float32), np.array(faces, np.int64)
