"""Prüfung der Stimme des KI-Helfers (Piper, offline).

    python3 tools/stimme-test.py <ausgabeordner>

1. Text fürs Vorlesen: Code, Links und Markdown fallen weg, gestreamte Antworten werden zu Sätzen.
2. Echte Sprachausgabe mit Piper über den Sprecher der Shell (Abspielen per Ersatz-„aplay“, das die
   Dateien einsammelt): automatische Antwort, „Vorlesen“-Knopf, Anhalten, Tempo.
3. Stimme nachladen über creative-ki-setup (wie in der App) und Hörproben aller Stimmen als WAV.
Erwartet Piper + Thorsten unter /usr/lib/creative-ki (ki/install-piper.sh) und den Lade-Helfer.
"""
import json
import os
import stat
import sys
import tempfile
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "shell"))
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()

# Ersatz-Abspieler: legt jede gespielte Datei in einen Ordner
gespielt = Path(tempfile.mkdtemp())
fake = Path(tempfile.mkdtemp())
(fake / "aplay").write_text(f"#!/bin/sh\nfor a; do f=\"$a\"; done\ncp \"$f\" {gespielt}/$(date +%s%N).wav\nsleep 0.05\n")
(fake / "aplay").chmod(0o755)
os.environ["PATH"] = f"{fake}:{os.environ['PATH']}"
for name in ("pw-play", "paplay"):
    assert not any((Path(p) / name).exists() for p in os.environ["PATH"].split(":") if p != str(fake)), \
        f"{name} gefunden – die Prüfung braucht den Ersatz-Abspieler"

from PySide6.QtCore import QEventLoop  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv[:1])
from creative_shell import stimme as st  # noqa: E402
from creative_shell.mainthread import install  # noqa: E402

install()

# ---- 1. Text -------------------------------------------------------------------------------
ANTWORT = """**Gern!** So listest du Dateien auf:

```bash
ls -la ~/Dokumente
echo "fertig"
```

Danach siehst du alle Dateien. Mehr dazu unter [der Anleitung](https://example.org/doku).
- Erstens: Terminal öffnen
- Zweitens: Befehl einfügen"""
erwartet = ["Gern!", "So listest du Dateien auf:", st.CODE_HINWEIS, "Danach siehst du alle Dateien.",
            "Mehr dazu unter der Anleitung.", "Erstens: Terminal öffnen", "Zweitens: Befehl einfügen"]
ganz = st.saetze(st.vorlesbar(ANTWORT))
assert ganz == erwartet, ganz
for schritt in (1, 3, 7, 50):
    z = st.Zerleger()
    teile = []
    for i in range(0, len(ANTWORT), schritt):
        teile += z.dazu(ANTWORT[i:i + schritt])
    teile += z.ende()
    assert teile == erwartet, (schritt, teile)
    assert not any("ls -la" in t or "echo" in t for t in teile)
print("Text fürs Vorlesen: ok")


def warten(cond, sek):
    ende = time.monotonic() + sek
    while time.monotonic() < ende and not cond():
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        time.sleep(0.02)
    return cond()


def wavs():
    return sorted(gespielt.glob("*.wav"))


def laut(path):
    with wave.open(str(path)) as w:
        frames = w.readframes(w.getnframes())
        dauer = w.getnframes() / w.getframerate()
    samples = memoryview(frames).cast("h")
    return dauer, max(abs(s) for s in samples)


# ---- 2. Sprechen ---------------------------------------------------------------------------
s = st.Sprecher()
assert s.available, "Piper oder Stimme fehlt"
assert s.voice == "thorsten", s.voice
s.beginn()
for i in range(0, len(ANTWORT), 5):          # wie beim Streamen aus dem Modell
    s.dazu(ANTWORT[i:i + 5])
s.ende()
assert warten(lambda: len(wavs()) >= len(erwartet) and not s.speaking, 90), (len(wavs()), s.speaking)
for w in wavs():
    dauer, spitze = laut(w)
    assert dauer > 0.3 and spitze > 1000, (w.name, dauer, spitze)
print(f"Automatisch vorgelesen: {len(wavs())} Sätze, Code übersprungen")
import shutil  # noqa: E402
shutil.copy(wavs()[0], OUT / "antwort-satz1.wav")

# Anhalten mitten im Vorlesen
for w in wavs():
    w.unlink()
s.speakText("Erster Satz. " * 12)
warten(lambda: len(wavs()) >= 2, 30)
s.stop()
n = len(wavs())
warten(lambda: False, 3)
assert len(wavs()) <= n + 1, ("nach Stopp weitergesprochen", n, len(wavs()))
assert not s.speaking
print("Anhalten: ok")

# Tempo: schneller = kürzer
dauern = {}
for tempo in (0.8, 1.4):
    for w in wavs():
        w.unlink()
    s.setSpeed(tempo)
    s.speakText("Das ist ein Satz, um das Tempo der Stimme zu prüfen.")
    assert warten(lambda: wavs() and not s.speaking, 30)
    dauern[tempo] = laut(wavs()[0])[0]
assert dauern[1.4] < dauern[0.8] * 0.9, dauern   # Pausen und Ränder bleiben gleich lang
print("Tempo:", dauern)

# Aus: nichts vorlesen
s.setSpeed(1.0)
s.setAutoRead(False)
for w in wavs():
    w.unlink()
s.beginn()
s.dazu("Das hier soll nicht gesprochen werden. ")
s.ende()
warten(lambda: False, 2)
assert not wavs(), "trotz „aus“ vorgelesen"
s.setAutoRead(True)
print("Vorlesen aus: ok")

# ---- 3. Stimmen nachladen + Hörproben --------------------------------------------------------
PROBE = "Hallo! Ich bin dein KI-Helfer. Frag mich etwas, und ich lese dir die Antwort vor."
liste = json.loads((Path(st.LIB) / "stimmen.json").read_text(encoding="utf-8"))
for key, info in liste.items():
    if not st.stimme_datei(info):
        s.installVoice(key)
        assert warten(lambda: s.loadingVoice == "", 300), "Laden hängt"
        assert st.stimme_datei(info), (key, s.status)
    s.setVoice(key)
    assert s.voice == key
    for w in wavs():
        w.unlink()
    s.speakText(PROBE)
    assert warten(lambda: len(wavs()) >= 2 and not s.speaking, 60), key
    # die Sätze einer Probe zu einer Datei zusammenfügen
    with wave.open(str(wavs()[0])) as w0:
        params = w0.getparams()
    with wave.open(str(OUT / f"stimme-{key}.wav"), "wb") as out:
        out.setparams(params)
        for w in wavs():
            with wave.open(str(w)) as wi:
                out.writeframes(wi.readframes(wi.getnframes()))
    print("Hörprobe:", key, info["name"])
s.quit()
print("Fertig.", sorted(p.name for p in OUT.iterdir()))
