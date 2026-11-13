"""Originalfoto auf die Vorderseite der Figur projizieren (schärfere, echtere Front).

TRELLIS backt die Textur aus einer Farbwolke – dabei gehen feine Details des Fotos
(Gesichter, Schrift, Muster) verloren. Hier wird das freigestellte Eingabebild
direkt auf alle Texel gelegt, die von vorne sichtbar sind:

1. Blickrichtung finden: Umriss der Figur von vorne/hinten/links/rechts mit der
   Maske des Fotos vergleichen (Überdeckung) und die Farben prüfen.
2. Für jeden Texel die 3D-Lage und Normale bestimmen (Rasterung im UV-Raum).
3. Sichtbar (Tiefenpuffer), zur Kamera gewandt und innerhalb der Maske →
   Fotofarbe einblenden, zu den Rändern hin weich auslaufend.

Nur numpy/PIL – läuft auf dem Prozessor und lässt sich ohne Grafikkarte prüfen.
"""

import numpy as np
from PIL import Image, ImageFilter

UP = np.array([0.0, 1.0, 0.0])
VIEWS = {"vorne": (0, 0, 1), "hinten": (0, 0, -1), "rechts": (1, 0, 0), "links": (-1, 0, 0)}


def _frame(d):
    d = np.asarray(d, float)
    r = np.cross(UP, d)
    return r / np.linalg.norm(r), d


def _project(points, view, fit):
    r, d = _frame(view)
    s, ox, oy = fit
    x = points @ r * s + ox
    y = -(points @ UP) * s + oy
    return x, y, points @ d


def _fit(vertices, view, mask):
    """Maßstab und Verschiebung, damit der Umriss die Fotomaske deckt (Höhe + Mitte)."""
    r, _ = _frame(view)
    xs, ys = vertices @ r, -(vertices @ UP)
    rows = np.where(mask.any(1))[0]
    cols = np.where(mask.any(0))[0]
    if len(rows) < 2 or len(cols) < 2:
        return None
    mh, mw = rows[-1] - rows[0] + 1, cols[-1] - cols[0] + 1
    sh, sw = ys.max() - ys.min(), xs.max() - xs.min()
    if sh <= 0 or sw <= 0:
        return None
    s = 0.5 * (mh / sh + mw / sw) if abs(mh / sh - mw / sw) / (mh / sh) < 0.25 else mh / sh
    ox = (cols[0] + cols[-1]) / 2 - s * (xs.min() + xs.max()) / 2
    oy = (rows[0] + rows[-1]) / 2 - s * (ys.min() + ys.max()) / 2
    return s, ox, oy


def _grow(a, n):
    """Maximum-Filter (Löcher im Punkt-Raster schließen) ohne scipy."""
    out = a.copy()
    for _ in range(n):
        p = np.pad(out, 1, mode="edge")
        out = np.maximum.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
    return out


def _splat(x, y, z, shape, fill):
    """Punkte in ein Raster: pro Pixel der größte Wert (näher an der Kamera)."""
    h, w = shape
    xi, yi = np.round(x).astype(np.int64), np.round(y).astype(np.int64)
    ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
    buf = np.full(h * w, fill, np.float32)
    np.maximum.at(buf, yi[ok] * w + xi[ok], z[ok].astype(np.float32))
    return buf.reshape(h, w)


def _dense_points(vertices, faces, scale, limit=3_000_000):
    """Punkte auf allen Dreiecken, dicht genug für Lücken unter einem Pixel (Bildmaßstab scale)."""
    tri = vertices[faces]
    edge = np.maximum.reduce([np.linalg.norm(tri[:, 1] - tri[:, 0], axis=1),
                              np.linalg.norm(tri[:, 2] - tri[:, 0], axis=1),
                              np.linalg.norm(tri[:, 2] - tri[:, 1], axis=1)]) * scale
    steps = np.clip(np.ceil(edge * 1.2).astype(np.int64), 1, 64)
    chunks, total = [vertices], len(vertices)
    for n in np.unique(steps):
        if n == 1 or total > limit:
            continue
        sel = np.where(steps == n)[0]
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        keep = (i + j) <= n
        bary = np.stack([1 - (i[keep] + j[keep]) / n, i[keep] / n, j[keep] / n], 1)
        pts = np.einsum("kc,fcd->fkd", bary, tri[sel]).reshape(-1, 3)
        chunks.append(pts)
        total += len(pts)
    return np.concatenate(chunks)


def _surface_samples(vertices, faces, uv, normals, size):
    """Für die Texel: (Texel-Index, 3D-Punkt, Normale) über ein Baryzentrik-Raster je Dreieck."""
    tri_uv = uv[faces] * (size - 1)                          # (F,3,2) in Texeln
    e1, e2 = tri_uv[:, 1] - tri_uv[:, 0], tri_uv[:, 2] - tri_uv[:, 0]
    edge = np.maximum.reduce([np.linalg.norm(e1, axis=1), np.linalg.norm(e2, axis=1),
                              np.linalg.norm(tri_uv[:, 2] - tri_uv[:, 1], axis=1)])
    steps = np.clip(np.ceil(edge * 1.5).astype(np.int64), 1, 96)
    for n in np.unique(steps):
        sel = np.where(steps == n)[0]
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        keep = (i + j) <= n
        b1, b2 = (i[keep] / n).astype(np.float32), (j[keep] / n).astype(np.float32)
        b0 = 1 - b1 - b2
        bary = np.stack([b0, b1, b2], 1)                     # (K,3)
        for start in range(0, len(sel), max(1, 400000 // len(bary))):
            f = sel[start:start + max(1, 400000 // len(bary))]
            fv = faces[f]
            p = np.einsum("kc,fcd->fkd", bary, vertices[fv]).reshape(-1, 3)
            nr = np.einsum("kc,fcd->fkd", bary, normals[fv]).reshape(-1, 3)
            t = np.einsum("kc,fcd->fkd", bary, tri_uv[f]).reshape(-1, 2)
            yield t, p, nr


def project_photo(vertices, faces, uv, normals, texture, photo, min_iou=0.80, log=print):
    """Gibt (neue Textur als PIL-Bild, Infos) zurück; bei schlechter Deckung die alte Textur."""
    vertices = np.asarray(vertices, np.float64)
    faces = np.asarray(faces, np.int64)
    uv = np.asarray(uv, np.float64)
    normals = np.asarray(normals, np.float64)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
    tex = np.asarray(texture.convert("RGB"), np.float32)
    size_h, size_w = tex.shape[:2]
    rgba = np.asarray(photo.convert("RGBA"), np.float32)
    ph, pw = rgba.shape[:2]
    alpha = rgba[..., 3] / 255.0
    mask = alpha > 0.5
    # Texturfarbe je Eckpunkt (für den Farbvergleich)
    vx = np.clip((uv[:, 0] % 1) * (size_w - 1), 0, size_w - 1).astype(np.int64)
    vy = np.clip((1 - uv[:, 1] % 1) * (size_h - 1), 0, size_h - 1).astype(np.int64)
    vcol = tex[vy, vx]

    best = None
    dense = None
    for name, view in VIEWS.items():
        fit = _fit(vertices, view, mask)
        if fit is None:
            continue
        if dense is None:
            dense = _dense_points(vertices, faces, fit[0])
        x, y, z = _project(dense, view, fit)
        sil = _grow(_splat(x, y, np.ones_like(z), (ph, pw), 0) > 0, 1)
        iou = (sil & mask).sum() / max(1, (sil | mask).sum())
        x, y, _z = _project(vertices, view, fit)
        facing = normals @ np.asarray(view, float) > 0.5
        xi = np.clip(np.round(x[facing]).astype(np.int64), 0, pw - 1)
        yi = np.clip(np.round(y[facing]).astype(np.int64), 0, ph - 1)
        inside = mask[yi, xi]
        err = float(np.abs(vcol[facing][inside] - rgba[yi[inside], xi[inside], :3]).mean()) if inside.any() else 255.0
        score = iou - err / 255.0
        log(f"Ansicht {name}: Deckung {iou:.2f}, Farbabweichung {err:.0f}")
        if best is None or score > best[0]:
            best = (score, name, view, fit, iou, err)
    if best is None or best[4] < min_iou:
        return texture, {"projiziert": False, "deckung": round(best[4], 3) if best else 0}
    _, name, view, fit, iou, err = best
    view = np.asarray(view, float)

    # Tiefenpuffer von vorne (Punkte = Eckpunkte + Flächenmitten, Löcher geschlossen)
    x, y, z = _project(dense, view, fit)
    depth = _grow(_splat(x, y, z, (ph, pw), -1e9), 1)
    span = float(np.ptp(vertices @ view)) or 1.0
    tol = 0.02 * span

    # Maske weich: Ränder auslaufen lassen (Kantenpixel des Fotos sind oft unsauber)
    soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))
                      .filter(ImageFilter.GaussianBlur(3)), np.float32) / 255.0

    acc = np.zeros((size_h * size_w, 3), np.float32)
    wsum = np.zeros(size_h * size_w, np.float32)
    cnt = np.zeros(size_h * size_w, np.float32)
    for t, p, nr in _surface_samples(vertices, faces, uv, normals, size_w):
        nr /= np.maximum(np.linalg.norm(nr, axis=1, keepdims=True), 1e-9)
        facing = nr @ view
        x, y, z = _project(p, view, fit)
        xi = np.clip(np.round(x).astype(np.int64), 0, pw - 1)
        yi = np.clip(np.round(y).astype(np.int64), 0, ph - 1)
        visible = z >= depth[yi, xi] - tol
        w = np.clip((facing - 0.30) / 0.40, 0, 1) * visible * soft[yi, xi]
        tx_all = np.clip(np.round(t[:, 0]).astype(np.int64), 0, size_w - 1)
        ty_all = np.clip(np.round((size_h - 1) - t[:, 1] * (size_h - 1) / (size_w - 1)).astype(np.int64), 0, size_h - 1)
        np.add.at(cnt, ty_all * size_w + tx_all, 1)
        ok = w > 0.02
        if not ok.any():
            continue
        # bilinear aus dem Foto
        xf, yf = np.clip(x[ok], 0, pw - 1.001), np.clip(y[ok], 0, ph - 1.001)
        x0, y0 = xf.astype(np.int64), yf.astype(np.int64)
        ax, ay = (xf - x0)[:, None], (yf - y0)[:, None]
        c = (rgba[y0, x0, :3] * (1 - ax) * (1 - ay) + rgba[y0, x0 + 1, :3] * ax * (1 - ay)
             + rgba[y0 + 1, x0, :3] * (1 - ax) * ay + rgba[y0 + 1, x0 + 1, :3] * ax * ay)
        idx = ty_all[ok] * size_w + tx_all[ok]
        np.add.at(acc, idx, c * w[ok, None])
        np.add.at(wsum, idx, w[ok])

    hit = wsum > 0
    flat = tex.reshape(-1, 3)
    out = flat.copy()
    weight = np.clip(wsum[hit] / np.maximum(cnt[hit], 1), 0, 1)[:, None]   # mittleres Gewicht je Texel
    out[hit] = flat[hit] * (1 - weight) + (acc[hit] / wsum[hit, None]) * weight
    result = Image.fromarray(np.clip(out.reshape(size_h, size_w, 3), 0, 255).astype(np.uint8))
    log(f"Foto projiziert: Ansicht {name}, Deckung {iou:.2f}, {int(hit.sum())} Texel")
    return result, {"projiziert": True, "ansicht": name, "deckung": round(float(iou), 3), "texel": int(hit.sum())}
