#!/bin/sh
# Prüft die Bluetooth-Einstellungen für Controller in Fedora 44 (wie im Abbild):
# BlueZ liest main.conf ohne Warnungen und übernimmt die Werte, udev- und modprobe-Dateien sind gültig.
set -eu
cd "$(dirname "$0")/.."
dnf install -y -q bluez kmod systemd-udev dbus-daemon python3 >/dev/null
cp /etc/bluetooth/main.conf /tmp/main.conf.orig
python3 image/bluetooth/bluez-anpassen.py /etc/bluetooth/main.conf
python3 image/bluetooth/bluez-anpassen.py /etc/bluetooth/main.conf      # zweimal: darf nichts doppeln
for k in FastConnectable JustWorksRepairing AutoEnable ReconnectAttempts ReconnectIntervals \
         MinConnectionInterval MaxConnectionInterval ConnectionLatency; do
  n=$(grep -c "^$k = " /etc/bluetooth/main.conf)
  [ "$n" = 1 ] || { echo "FEHLER: $k steht $n-mal in main.conf"; exit 1; }
done
diff -u /tmp/main.conf.orig /etc/bluetooth/main.conf | grep '^[+-][^+-]' || true
# BlueZ selbst liest die Datei (ohne Adapter: es meldet nur falsche Schlüssel/Werte und fehlende Hardware)
mkdir -p /run/dbus
dbus-daemon --system --fork
out=$(timeout 4 /usr/libexec/bluetooth/bluetoothd -n -d 2>&1 || true)
echo "$out" | grep -iE "main.conf|Unknown key|invalid|error" | head -20 || true
if echo "$out" | grep -iE "Unknown key|Invalid value|not supported|out of range" | grep -v "Bluetooth management interface"; then
  echo "FEHLER: BlueZ beanstandet main.conf"; exit 1
fi
echo "$out" | grep -q "Bluetooth daemon" || { echo "FEHLER: bluetoothd startet nicht"; echo "$out" | head; exit 1; }
# udev-Regel und modprobe-Einstellung
install -Dm644 image/bluetooth/50-creative-bluetooth.rules /usr/lib/udev/rules.d/50-creative-bluetooth.rules
udevadm verify /usr/lib/udev/rules.d/50-creative-bluetooth.rules
install -Dm644 image/bluetooth/creative-bluetooth.conf /usr/lib/modprobe.d/creative-bluetooth.conf
modprobe --showconfig | grep -q "options btusb enable_autosuspend=0" || { echo "FEHLER: modprobe-Option fehlt"; exit 1; }
echo "Bluetooth-Einstellungen: ok"
