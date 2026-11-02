#!/bin/bash
# Installer-Look prüfen: Anaconda im virtuellen Bildschirm starten und fotografieren
set +e
dnf install -y -q anaconda-gui anaconda-install-env-deps xorg-x11-server-Xvfb ImageMagick dbus-daemon google-noto-sans-fonts liberation-sans-fonts >/dev/null 2>&1
rpm -q anaconda-gui
mkdir -p /run/install/updates/usr/share/anaconda/pixmaps /etc/gtk-3.0
cp image/netinstall/installer/anaconda-gtk.css /run/install/updates/
cp image/netinstall/installer/pixmaps/*.png /run/install/updates/usr/share/anaconda/pixmaps/
cp image/netinstall/installer/pixmaps/*.png /usr/share/anaconda/pixmaps/
printf '[Settings]\ngtk-application-prefer-dark-theme=1\n' > /etc/gtk-3.0/settings.ini
cat > /tmp/ks.cfg <<'KS'
lang de_DE.UTF-8
keyboard de
timezone Europe/Berlin
KS
Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 &
sleep 2
export DISPLAY=:99 LANG=de_DE.UTF-8 XDG_RUNTIME_DIR=/tmp/xdg; mkdir -p /tmp/xdg; chmod 700 /tmp/xdg
mkdir -p /tmp/sys
dbus-daemon --system --fork 2>/dev/null
(anaconda --dirinstall /tmp/sys --graphical --lang de_DE.UTF-8 > /tmp/ana.out 2>&1 &)
sleep 75
mkdir -p shots
import -window root /tmp/s1.png
magick /tmp/s1.png -resize 1100x -quality 75 /tmp/s.jpg 2>/dev/null || convert /tmp/s1.png -resize 1100x -quality 75 /tmp/s.jpg
tail -25 /tmp/ana.out; tail -20 /tmp/anaconda.log 2>/dev/null
grep -i "css\|error" /tmp/anaconda.log /tmp/*.log 2>/dev/null | grep -i css | head
echo BILD-ANFANG; base64 /tmp/s.jpg | sed "s/^/B64:/"; echo BILD-ENDE
