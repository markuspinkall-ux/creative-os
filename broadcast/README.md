# Creative Broadcast

Rauschfreies Mikrofon und virtueller Greenscreen für Creative OS – sparsam im Verbrauch.

- **Mikrofon:** DeepFilterNet (KI-Rauschentfernung, CPU) als PipeWire-Filter → neue Eingabe
  „Creative Mikrofon (rauschfrei)“, wird beim Einschalten automatisch Standard. Stärke einstellbar.
  Ohne DeepFilterNet: WebRTC-Rauschunterdrückung als Ersatz.
- **Kamera:** Robust Video Matting (KI-Freistellung bis in die Haare) → Hintergrund unscharf, eigenes Bild
  oder echtes Grün → virtuelle Kamera „Creative Kamera“ (v4l2loopback). „Sparsam“ rechnet intern in 640×360,
  „Beste Qualität“ in 1280×720. Gerechnet wird **nur, solange ein Programm die Kamera benutzt** – sonst wird die
  echte Kamera freigegeben (Licht aus) und es entsteht keine Last.
- Mit NVIDIA-Grafikkarte und CUDA-fähiger ONNX Runtime rechnet die Freistellung auf der Grafikkarte.

Grundlagen: DeepFilterNet (MIT/Apache-2.0), Robust Video Matting (GPL-3.0), ONNX Runtime, OpenCV, v4l2loopback, PipeWire.
