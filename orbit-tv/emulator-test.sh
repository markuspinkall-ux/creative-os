#!/bin/bash
# Läuft im Android-TV-Emulator (CI): installieren, starten, Fotos machen.
set -x
mkdir -p fotos
adb install -r OrbitTV.apk
adb shell am start -n de.orbitos.tv/.MainActivity
sleep 12
adb exec-out screencap -p > fotos/tv-1-liste.png
adb shell input keyevent KEYCODE_DPAD_DOWN; sleep 1
adb shell input keyevent KEYCODE_DPAD_DOWN; sleep 1
adb exec-out screencap -p > fotos/tv-2-auswahl.png
for i in 1 2 3 4 5; do adb shell input keyevent KEYCODE_DPAD_RIGHT; sleep 1; done
adb exec-out screencap -p > fotos/tv-3-joyn.png
adb shell input keyevent KEYCODE_MENU; sleep 2
adb exec-out screencap -p > fotos/tv-4-optionen.png
adb shell input keyevent KEYCODE_BACK; sleep 1
adb shell input keyevent KEYCODE_BACK; sleep 2
adb exec-out screencap -p > fotos/tv-5-sender.png
adb logcat -d -s AndroidRuntime:E ExoPlayerImplInternal:E MediaCodecVideoRenderer:E > fotos/log.txt || true
adb shell pidof de.orbitos.tv && echo "App läuft noch" || echo "APP ABGESTÜRZT"
