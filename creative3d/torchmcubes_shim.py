"""Ersatz für torchmcubes (TripoSR) auf Basis von scikit-image.

torchmcubes muss mit dem CUDA-Compiler gebaut werden; scikit-image gibt es
fertig. Gleiches Verhalten wie torchmcubes.marching_cubes(vol, threshold):
Eckpunkte in der Reihenfolge (x, y, z) = (Achse 2, Achse 1, Achse 0) und
Dreiecke so gewendet, dass sie nach außen zeigen (innen = Werte über der Schwelle).
"""

import numpy as np


def mc_numpy(volume, threshold):
    from skimage.measure import marching_cubes as _mc
    vol = np.asarray(volume, dtype=np.float32)
    if not (vol.min() < threshold < vol.max()):
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.int64)
    verts, faces, _normals, _values = _mc(vol, level=threshold)
    verts = verts[:, ::-1].copy()              # (Achse 2, 1, 0) wie torchmcubes
    # Achsentausch und scikit-image-Wicklung heben sich auf: Dreiecke zeigen so nach außen
    return verts.astype(np.float32), faces.astype(np.int64)


def marching_cubes(volume, threshold):
    import torch
    verts, faces = mc_numpy(volume.detach().float().cpu().numpy(), float(threshold))
    return torch.from_numpy(verts), torch.from_numpy(faces)
