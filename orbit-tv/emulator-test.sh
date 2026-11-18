#!/bin/bash
# Läuft im Android-TV-Emulator (CI): installieren, starten, Fotos machen.
set -x
mkdir -p fotos
adb shell wm density 320 && sleep 3
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
# Radio-Gruppe (Direktwahl per Intent)
adb shell am start -n de.orbitos.tv/.MainActivity --es gruppe Radio; sleep 3
adb exec-out screencap -p > fotos/tv-6-radio.png
adb shell input keyevent KEYCODE_DPAD_CENTER; sleep 10
adb exec-out screencap -p > fotos/tv-7-radio-laeuft.png
# Joyn im Web-Player
adb shell am start -n de.orbitos.tv/.MainActivity --es sender sat1; sleep 20
adb exec-out screencap -p > fotos/tv-8-joyn-web.png
for i in 1 2 3 4 5 6; do adb shell input keyevent KEYCODE_DPAD_RIGHT; adb shell input keyevent KEYCODE_DPAD_DOWN; done; sleep 1
adb exec-out screencap -p > fotos/tv-9-zeiger.png
adb shell input keyevent KEYCODE_BACK; sleep 1; adb shell input keyevent KEYCODE_BACK; sleep 2
adb logcat -d -s AndroidRuntime:E ExoPlayerImplInternal:E MediaCodecVideoRenderer:E > fotos/log.txt || true
adb shell pidof de.orbitos.tv && echo "App läuft noch" || echo "APP ABGESTÜRZT"
