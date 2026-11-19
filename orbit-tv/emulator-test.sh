#!/bin/bash
# Läuft im Android-TV-Emulator (CI): installieren, starten, Fotos machen.
set -x
mkdir -p fotos
A=de.orbitos.tv/.MainActivity
foto() { adb exec-out screencap -p > "fotos/$1.png"; }
key() { adb shell input keyevent "$@"; sleep 1; }
adb shell wm density 320 && sleep 3
adb install -r OrbitTV.apk
adb shell am start -n $A
sleep 15
foto tv-1-start
key KEYCODE_DPAD_RIGHT KEYCODE_DPAD_RIGHT
sleep 2
foto tv-2-kachel
key KEYCODE_MENU
sleep 1
foto tv-3-optionen
key KEYCODE_BACK
# Dialog „Neuer Sender“
adb shell am start -n $A --es dialog neu; sleep 3
foto tv-4-neuer-sender
key KEYCODE_BACK; key KEYCODE_BACK; sleep 1
# Eigenen Sender anlegen (Testadresse: Das Erste) und zuordnen
adb shell am start -n $A --es neu_name "Mein\ Sender" --es neu_url "https://daserste-live.ard-mcdn.de/daserste/live/hls/de/master.m3u8"; sleep 4
foto tv-5-eigene
key KEYCODE_MENU
key KEYCODE_DPAD_DOWN KEYCODE_DPAD_DOWN KEYCODE_DPAD_CENTER
sleep 1
foto tv-6-zuordnen
key KEYCODE_BACK
# Vollbild und Umschalten
adb shell am start -n $A --es gruppe ZDF --es sender zdf; sleep 12
foto tv-7-vollbild
key KEYCODE_DPAD_DOWN
sleep 8
foto tv-8-umschalten
key KEYCODE_BACK
sleep 2
foto tv-9-zurueck
adb logcat -d -s AndroidRuntime:E ExoPlayerImplInternal:E > fotos/log.txt || true
adb shell pidof de.orbitos.tv && echo "App läuft noch" || echo "APP ABGESTÜRZT"
