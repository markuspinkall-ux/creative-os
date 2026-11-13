"""KI-Upscaling für das Kamerabild (auf 1080p).

Modell: 2xNomosUni_span_multijpg von Philip Hofmann (Helaman), CC-BY-4.0,
https://github.com/Phhofm/models – SPAN-Netz, für JPEG-Artefakte trainiert
(passt zu MJPG-Webcams). Läuft nur auf der Grafikkarte (CUDA, FP16); auf dem
Prozessor wäre es für Live-Bilder zu langsam und wird daher nicht angeboten.

Stufen:
  schnell – Bild zuerst auf 960×540 verkleinert, KI verdoppelt auf 1920×1080
  beste   – KI verdoppelt das volle Kamerabild, danach sauber auf 1080p verkleinert
"""

import sys
from pathlib import Path

MODEL = Path("/usr/share/creative-broadcast/2xNomosUni_span_multijpg_fp16.onnx")
OUT_W, OUT_H = 1920, 1080


def available():
    """(ja/nein, Grund) – ob KI-Upscaling auf diesem Rechner geht."""
    if not MODEL.exists():
        return False, "KI-Modell fehlt"
    try:
        import onnxruntime as ort
    except ImportError:
        return False, "ONNX Runtime fehlt"
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        return False, "nur mit NVIDIA-Grafikkarte"
    return True, ""


class Upscaler:
    def __init__(self, level, providers=None):
        import numpy as np
        import onnxruntime as ort
        self.np = np
        self.level = level
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if providers is None:
            providers = [("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC",
                                                    "do_copy_in_default_stream": True})]
        self.sess = ort.InferenceSession(str(MODEL), sess_options=opts, providers=providers)
        self.engine = self.sess.get_providers()[0].replace("ExecutionProvider", "")
        inp = self.sess.get_inputs()[0]
        self.input = inp.name
        self.dtype = np.float16 if "float16" in inp.type else np.float32
        print(f"Creative Broadcast: Upscaling {level} über {self.engine}", file=sys.stderr)

    def needed(self, frame):
        return frame.shape[0] < OUT_H

    def run(self, frame_bgr):
        import cv2
        np = self.np
        src = frame_bgr
        if self.level == "schnell" and (src.shape[1], src.shape[0]) != (OUT_W // 2, OUT_H // 2):
            src = cv2.resize(src, (OUT_W // 2, OUT_H // 2), interpolation=cv2.INTER_AREA)
        x = src[:, :, ::-1].transpose(2, 0, 1)[None].astype(self.dtype) * self.dtype(1 / 255)
        y = self.sess.run(None, {self.input: x})[0][0]
        y = np.clip(y.transpose(1, 2, 0)[:, :, ::-1].astype(np.float32) * 255.0 + 0.5, 0, 255).astype(np.uint8)
        if (y.shape[1], y.shape[0]) != (OUT_W, OUT_H):
            y = cv2.resize(y, (OUT_W, OUT_H), interpolation=cv2.INTER_AREA)
        return y
