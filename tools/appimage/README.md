# Gibeon-Apps als AppImage (für andere Linux-Systeme)

Gebaut von `.github/workflows/appimages.yml`, veröffentlicht im Release **appimages**.

| AppImage | Inhalt |
|---|---|
| `Gibeon-Studio-x86_64.AppImage` | Studio (Aufnehmen und Streamen) samt **Broadcast** (Rauschfilter fürs Mikrofon, Hintergrund der Webcam). `--broadcast` öffnet Broadcast direkt. Aktualisiert sich selbst (Leiste oben in Studio). |
| `Gibeon-3D-Studio-x86_64.AppImage` | 3D Studio (Foto → 3D-Figur mit TRELLIS). |

## Was das System mitbringen muss

**Studio und Broadcast**
- PipeWire (Standard bei Fedora, Ubuntu ab 22.10, Arch, openSUSE …) und xdg-desktop-portal (Bildschirmfreigabe)
- GStreamer mit den Plugin-Paketen *good*, *bad*, *ugly* und *libav* sowie dem PipeWire-Plugin
- ffmpeg
- für die virtuelle Kamera „Gibeon Kamera“: das Kernelmodul **v4l2loopback**, geladen mit
  `sudo modprobe v4l2loopback video_nr=42 card_label="Gibeon Kamera" exclusive_caps=1`

**3D Studio**
- NVIDIA-Grafikkarte (mind. 12 GB), NVIDIA-Treiber, **podman** und das **NVIDIA Container Toolkit** (CDI)
- beim ersten Start werden rund 18 GB geladen
