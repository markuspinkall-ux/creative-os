#!/bin/bash
# Schnelle Prüfungen in einem frischen Fedora (Werkzeug für die Entwicklung)
set +e
dnf install -y -q xorriso squashfs-tools curl >/dev/null 2>&1
base=https://download.fedoraproject.org/pub/fedora/linux/releases/44/Everything/x86_64/iso
iso=$(curl -fsSL "$base/" | grep -o "Fedora-Everything-netinst-x86_64-[0-9.-]*\.iso" | head -n1)
echo "ISO: $iso"
curl -fsSL -o /tmp/n.iso "$base/$iso"
xorriso -osirrox on -indev /tmp/n.iso -extract /images/install.img /tmp/install.img -extract /EFI/BOOT/grub.cfg /tmp/grub.cfg >/dev/null 2>&1
grep -n "linux" /tmp/grub.cfg | head -4
cd /tmp && unsquashfs -q -d /tmp/r /tmp/install.img 2>/dev/null
# install.img kann ein weiteres rootfs-Abbild enthalten
if [ -f /tmp/r/LiveOS/rootfs.img ]; then mkdir -p /tmp/rr; unsquashfs -q -d /tmp/rr /tmp/r/LiveOS/rootfs.img 2>/dev/null || (dnf install -y -q e2fsprogs >/dev/null; debugfs -R "rdump /usr/share/anaconda /tmp" /tmp/r/LiveOS/rootfs.img); R=/tmp/rr; else R=/tmp/r; fi
ls $R/usr/share/ | grep -i "anaconda\|cockpit" 
ls $R/usr/share/cockpit 2>/dev/null | head
ls $R/usr/share/anaconda/ 2>/dev/null | head -30
echo "=== fedora.css"; cat $R/usr/share/anaconda/pixmaps/fedora.css 2>/dev/null || find / -name fedora.css -path "*anaconda*" -exec cat {} \; 2>/dev/null | head -50
echo "=== webui?"; ls $R/usr/share/cockpit/anaconda-webui 2>/dev/null | head -3; ls $R/usr/libexec/ | grep -i webui
grep -rn "webui" $R/usr/share/anaconda/*.conf $R/etc/anaconda 2>/dev/null | head
ls $R/etc/anaconda/profile.d 2>/dev/null | head
