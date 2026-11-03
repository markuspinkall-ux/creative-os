#!/bin/bash
# Starttest für Creative OS (läuft auf GitHub): Abbild → virtuelle Festplatte → QEMU → prüfen.
set -u
W="$PWD/boottest"; mkdir -p "$W"
IMG=ghcr.io/markuspinkall-ux/creative-os:amd-testing

if [ "$1" = build ]; then
    echo "$GH_TOKEN" | sudo podman login ghcr.io -u "$ACTOR" --password-stdin >/dev/null
    sudo podman pull -q "$IMG" >/dev/null || exit 1
    ssh-keygen -q -t ed25519 -N "" -f "$W/key"
    cat > "$W/config.toml" <<TOML
[[customizations.user]]
name = "tester"
password = "creative-test"
key = "$(cat "$W/key.pub")"
groups = ["wheel"]

[customizations.kernel]
append = "systemd.wants=sshd.service"
TOML
    mkdir -p "$W/out"
    sudo podman run --rm --privileged --security-opt label=type:unconfined_t \
        -v "$W/out:/output" -v "$W/config.toml:/config.toml:ro" \
        -v /var/lib/containers/storage:/var/lib/containers/storage \
        quay.io/centos-bootc/bootc-image-builder:latest --type qcow2 --rootfs btrfs "$IMG" 2>&1 | tail -15
    sudo chown -R "$USER" "$W/out"
    ls -la "$W/out/qcow2/disk.qcow2" || exit 1
    sudo podman rmi -f "$IMG" >/dev/null 2>&1
    exit 0
fi

# ---- run ---------------------------------------------------------------------------------
fail() { echo "STARTTEST FEHLGESCHLAGEN: $1"; shot final; exit 1; }
qmp() { printf '{"execute":"qmp_capabilities"}\n%s\n' "$1" | timeout 5 socat - UNIX-CONNECT:"$W/qmp.sock" >/dev/null 2>&1; }
shot() { dev=${2:+,\"device\":\"$2\"}; qmp "{\"execute\":\"screendump\",\"arguments\":{\"filename\":\"$W/$1.ppm\"$dev}}"; sleep 1
         [ -f "$W/$1.ppm" ] || return 0
         pnmtopng "$W/$1.ppm" > "$W/$1.png" 2>/dev/null
         # verkleinert ins Protokoll (zum Ansehen ohne Download)
         pnmscale -width 1000 "$W/$1.ppm" 2>/dev/null | pnmtopng 2>/dev/null | base64 | sed "s/^/B64$1:/"
         rm -f "$W/$1.ppm"; echo "Bildschirmfoto: $1.png"; }
SSH="ssh -i $W/key -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o LogLevel=ERROR tester@127.0.0.1"
command -v socat >/dev/null || sudo apt-get install -y -qq socat >/dev/null

qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -m 6144 -smp 4 \
    -drive file="$W/out/qcow2/disk.qcow2",if=virtio,format=qcow2 \
    -nic user,model=virtio-net-pci,hostfwd=tcp::2222-:22 \
    -device virtio-vga,id=gpu0 -device virtio-gpu-pci,id=gpu1 -device virtio-gpu-pci,id=gpu2 -display none -qmp unix:"$W/qmp.sock",server,nowait \
    -serial file:"$W/serial.log" -daemonize -pidfile "$W/qemu.pid" || fail "QEMU startet nicht"

echo "Warte auf das System …"
for i in $(seq 1 90); do $SSH true 2>/dev/null && break; sleep 5; done
$SSH true 2>/dev/null || fail "System nicht erreichbar (kein SSH nach 7 Minuten)"
shot login
echo "System läuft. Anmeldung wird automatisch durchgeführt …"
$SSH "echo creative-test | sudo -S sh -c 'mkdir -p /etc/sddm.conf.d && printf \"[Autologin]\nUser=tester\nSession=creative.desktop\n\" > /etc/sddm.conf.d/zz-starttest.conf && systemctl restart sddm'" 2>&1 | tail -3
sleep 100
shot desktop
# drei Monitore: jeder braucht eigenen Hintergrund und eigene Taskleiste
shot monitor2 gpu1
shot monitor3 gpu2
cat > "$W/dump.js" <<'JS'
for (const o of workspace.screens) console.warn("CREATIVE-MM SCREEN", o.name, o.geometry.x, o.geometry.y, o.geometry.width, o.geometry.height);
for (const w of workspace.stackingOrder) console.warn("CREATIVE-MM WIN", JSON.stringify(w.caption), "out=" + (w.output ? w.output.name : "?"), w.x, w.y, w.width, w.height);
JS
scp -i "$W/key" -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$W/dump.js" tester@127.0.0.1:/tmp/dump.js
echo "--- Monitore und Flächen:"
$SSH 'export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
id=$(gdbus call --session --dest org.kde.KWin --object-path /Scripting --method org.kde.kwin.Scripting.loadScript /tmp/dump.js mm | grep -o "[0-9]\+" | head -1)
gdbus call --session --dest org.kde.KWin --object-path /Scripting/Script$id --method org.kde.kwin.Script.run >/dev/null; sleep 2
journalctl --user -b --no-pager 2>/dev/null | grep -o "CREATIVE-MM.*"; journalctl -b --no-pager 2>/dev/null | grep -o "CREATIVE-MM.*" | sort -u' 2>&1 | sort -u | head -40
$SSH 'journalctl -b --no-pager -t creative-shell -t creative-notifyd -t creative-session 2>/dev/null | tail -40' > "$W/session.log" 2>&1
$SSH 'journalctl -b --no-pager -p err 2>/dev/null | tail -60' > "$W/errors.log" 2>&1
echo "--- Willkommen-Protokoll:"; $SSH 'cat ~/.cache/creative-welcome.log 2>/dev/null | tail -20; pgrep -af creative_welcome' 2>&1 | tail -22
state=$($SSH 'cat /tmp/creative-shell-state-$(id -u) 2>/dev/null')
shell=$($SSH 'pgrep -u tester -f "python3 -m creative_shell" | head -1')
notif=$($SSH 'pgrep -u tester -f "python3 -m creative_notify" | head -1')
health=$($SSH 'systemctl is-active creative-session-health.service; cat /var/lib/creative-os/last-good 2>/dev/null | head -c 12')
echo "Oberfläche: ${shell:-läuft NICHT}  ·  Zustand: ${state:-unbekannt}  ·  Benachrichtigungen: ${notif:-läuft nicht}"
echo "Gesundheitsprüfung: $health"
[ -n "$shell" ] || fail "Die Oberfläche (Taskleiste) läuft nicht"
$SSH 'modinfo v4l2loopback >/dev/null 2>&1' || fail "Die virtuelle Kamera (v4l2loopback) fehlt im Abbild"
echo "Treiber-Signatur: $($SSH 'modinfo -F signer v4l2loopback 2>/dev/null')"
welcome=$($SSH 'pgrep -u tester -f creative_welcome | head -1')
[ -n "$welcome" ] || fail "Das Willkommen-Fenster läuft nicht"
$SSH 'grep -q "of null\|Traceback" ~/.cache/creative-welcome.log 2>/dev/null' && fail "Fehler im Willkommen-Fenster (siehe Protokoll)"
[ "$state" = "ok" ] || fail "Die Oberfläche läuft nicht stabil (Zustand: ${state:-unbekannt})"
echo "STARTTEST BESTANDEN"
shot final
kill "$(cat "$W/qemu.pid")" 2>/dev/null
exit 0
