#!/usr/bin/bash
# Macht aus dem Creative-OS-Abbild eine Live-Umgebung (nach dem Beispiel von Titanoboa/Bazzite).
set -exo pipefail
VARIANT="${1:-amd}"
IMAGE="ghcr.io/markuspinkall-ux/creative-os:${VARIANT}"
SRC=/src/live

chmod 755 /usr/bin/creative-installer /usr/libexec/creative-installer-helper /usr/libexec/creative-shell-supervisor
mkdir -p "$(realpath /root)"
mount -o remount,rw /proc/sys 2>/dev/null || true

# 1) Das Abbild, das installiert wird, liegt auf der ISO (Installation ohne Internet)
podman pull "$IMAGE"

# 2) Start vom USB-Stick: Live-Initramfs
dnf install -y dracut-live
kernel=$(find /usr/lib/modules -maxdepth 1 -mindepth 1 -type d -printf '%P\n' | sort -V | tail -1)
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "dmsquash-live dmsquash-live-autooverlay" \
    "/usr/lib/modules/${kernel}/initramfs.img" "${kernel}"

# 3) Live-Benutzer (liveuser) und Anmeldung ohne Passwort
dnf install -y livesys-scripts
sed -i 's/^livesys_session=.*/livesys_session=kde/' /etc/sysconfig/livesys
systemctl enable livesys.service livesys-late.service
install -Dm755 "$SRC/creative-live-setup" /usr/libexec/creative-live-setup
install -Dm644 "$SRC/creative-live-setup.service" /usr/lib/systemd/system/creative-live-setup.service
systemctl enable creative-live-setup.service
install -Dm644 "$SRC/49-creative-installer.rules" /etc/polkit-1/rules.d/49-creative-installer.rules

# 4) Anaconda als Unterbau der Installation (+ Fedora-Installer für Sonderfälle, im Graphit-Look)
dnf install -y --allowerasing anaconda-live anaconda-core libblockdev-btrfs libblockdev-lvm libblockdev-dm openssl
mkdir -p /usr/share/anaconda/pixmaps /etc/anaconda/conf.d
cp /src/anaconda-look/anaconda-gtk.css /usr/share/anaconda/creative-gtk.css
cp /src/anaconda-look/pixmaps/*.png /usr/share/anaconda/pixmaps/
printf '[User Interface]\ncustom_stylesheet = /usr/share/anaconda/creative-gtk.css\n' > /etc/anaconda/conf.d/99-creative-os.conf
echo "Creative OS release $(. /etc/os-release; echo "$VERSION_ID")" > /etc/system-release

# 5) Selbsttest der Installations-Oberfläche
QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp HOME=/tmp/live-home timeout 60 /usr/bin/creative-installer --selftest

# 6) Was Titanoboa/image-builder zum Bauen der ISO braucht
dnf install -y grub2-efi-x64-cdboot xorriso isomd5sum
mkdir -p /boot/efi
cp -av /usr/lib/efi/*/*/EFI /boot/efi/ 2>/dev/null || cp -av /usr/lib/bootupd/updates/EFI /boot/efi/
cp -v /boot/efi/EFI/fedora/grubx64.efi /boot/efi/EFI/BOOT/fbx64.efi || true
mkdir -p /usr/lib/bootc-image-builder
cp "$SRC/iso.yaml" /usr/lib/bootc-image-builder/iso.yaml

# 7) /var/tmp groß genug (ostree braucht beim Installieren viel Platz dort)
rm -rf /var/tmp || :
mkdir -p /var/tmp
cat >/etc/systemd/system/var-tmp.mount <<'UNIT'
[Unit]
Description=Größeres tmpfs für /var/tmp in der Live-Umgebung

[Mount]
What=tmpfs
Where=/var/tmp
Type=tmpfs
Options=size=50%%,nr_inodes=1m

[Install]
WantedBy=local-fs.target
UNIT
systemctl enable var-tmp.mount

# Live-Umgebung braucht keine automatischen Updates und keinen Greenboot-Rückfall
systemctl disable rpm-ostreed-automatic.timer greenboot-healthcheck.service 2>/dev/null || true
dnf clean all
