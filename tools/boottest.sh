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
# Stand dieses Branches vorab einspielen (vorübergehend beschreibbares /usr, bis zum Neustart)
if [ "${BRANCH_EINSPIELEN:-1}" = 1 ] && [ -d shell/creative_shell ]; then
    echo "--- Branch-Stand wird in die VM eingespielt …"
    tar -czf "$W/branch.tgz" shell/creative_shell shell/session/creative-shell-supervisor users/creative-users-helper login/creative
    scp -i "$W/key" -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$W/branch.tgz" tester@127.0.0.1:/tmp/branch.tgz
    $SSH "echo creative-test | sudo -S sh -c 'rpm-ostree usroverlay >/dev/null 2>&1 || ostree admin unlock >/dev/null 2>&1; mkdir -p /tmp/b && tar -xzf /tmp/branch.tgz -C /tmp/b && rm -rf /usr/lib/creative-shell/creative_shell && cp -r /tmp/b/shell/creative_shell /usr/lib/creative-shell/ && install -m755 /tmp/b/shell/session/creative-shell-supervisor /usr/libexec/creative-shell-supervisor && install -m755 /tmp/b/users/creative-users-helper /usr/libexec/creative-users-helper && cp /tmp/b/login/creative/Main.qml /usr/share/sddm/themes/creative/Main.qml && echo eingespielt'" 2>&1 | tail -2
fi
$SSH "echo creative-test | sudo -S sh -c 'python3 -m venv /tmp/ps >/dev/null 2>&1 && /tmp/ps/bin/pip -q install py-spy >/dev/null 2>&1; ls /tmp/ps/bin/py-spy'" 2>&1 | tail -1
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
echo "--- Umgebung der Shell (erstes Konto):"
$SSH 'p=$(pgrep -u tester -f "python3 -m creative_shell" | head -1); tr "\0" "\n" < /proc/$p/environ | cut -c1-90 | sort' 2>&1 | head -40
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
shot final

# ---- Zweites Konto: ohne Passwort, wie in der Systemsteuerung angelegt ----------------------
if [ "${ZWEITKONTO:-1}" = 1 ]; then
    echo "--- Zweites Konto „frau“ (ohne Passwort) wird angelegt …"
    $SSH "echo creative-test | sudo -S sh -c 'PKEXEC_UID=\$(id -u tester) /usr/libexec/creative-users-helper add frau \"Anna Test\" 0 </dev/null'" 2>&1 | tail -3
    $SSH "getent passwd frau; id frau; sudo -n true 2>/dev/null; echo creative-test | sudo -S passwd -S frau; cat /var/lib/creative-os/ohne-passwort" 2>&1 | tail -5
    # Anmeldemaske mit „frau“ als zuletzt gewähltem Konto
    $SSH "echo creative-test | sudo -S sh -c 'rm -f /etc/sddm.conf.d/zz-starttest.conf; mkdir -p /var/lib/sddm; printf \"[Last]\nUser=frau\nSession=/usr/share/wayland-sessions/creative.desktop\n\" > /var/lib/sddm/state.conf; chown sddm: /var/lib/sddm/state.conf 2>/dev/null; systemctl restart sddm'" 2>&1 | tail -2
    sleep 40
    shot anmeldung-frau
    R="echo creative-test | sudo -S"
    haenger=0
    for runde in 1 2 3; do
        $SSH "echo creative-test | sudo -S sh -c 'printf \"[Autologin]\nUser=frau\nSession=creative.desktop\n\" > /etc/sddm.conf.d/zz-starttest.conf && systemctl restart sddm'" 2>&1 | tail -2
        sleep 100
        shot desktop-frau-$runde
        zeichnet=$($SSH "$R sh -c 'p=\$(pgrep -u frau -f \"python3 -m creative_shell\" | head -1); cat /proc/\$p/task/*/comm 2>/dev/null | grep -c QSGRenderThr; echo; cat /proc/\$p/wchan'" 2>/dev/null | grep -v password | tr '\n' ' ')
        echo "Runde $runde: Render-Threads/Haupt-Thread: $zeichnet"
        case "$zeichnet" in 0*)
            haenger=$((haenger + 1))
            echo "--- Runde $runde hängt – Python-Stapel (py-spy):"
            $SSH "$R sh -c 'p=\$(pgrep -u frau -f \"python3 -m creative_shell\" | head -1); for t in /proc/\$p/task/*; do echo \$(cat \$t/comm) \$(cat \$t/wchan); done; /tmp/ps/bin/py-spy dump --native --pid \$p 2>&1 | head -120'" 2>&1 | grep -v "password for" | head -150
            sleep 60
            echo "--- 60 s später:"
            $SSH "$R sh -c 'p=\$(pgrep -u frau -f \"python3 -m creative_shell\" | head -1); cat /proc/\$p/task/*/comm | sort | uniq -c; /tmp/ps/bin/py-spy dump --pid \$p 2>&1 | head -40'" 2>&1 | grep -v "password for" | head -60
            ;;
        esac
        $SSH "$R journalctl -b --no-pager -t creative-shell _UID=\$(id -u frau) | tail -15" 2>&1 | grep -v "password for\|MESA\|portal" | tail -15
    done
    echo "Zweitkonto: $haenger von 3 Anmeldungen ohne gezeichnete Oberfläche"
    shot desktop-frau
    $SSH "$R sh -c 'u=\$(id -u frau); echo Sitzungen:; loginctl list-sessions --no-legend; echo Prozesse:; pgrep -u frau -af \"creative|kwin|python3\" | head -30; echo Zustand: \$(cat /tmp/creative-shell-state-\$u 2>/dev/null); echo Home:; ls -la ~frau ~frau/.config ~frau/.config/creative-os 2>&1 | head -60; echo Willkommen-Log:; tail -30 ~frau/.cache/creative-welcome.log 2>&1'" > "$W/frau.log" 2>&1
    $SSH "$R journalctl -b --no-pager _UID=\$(id -u frau) 2>/dev/null | tail -250" > "$W/frau-journal.log" 2>&1
    $SSH "$R journalctl -b --no-pager -u sddm 2>/dev/null | tail -60" > "$W/sddm.log" 2>&1
    echo "--- Zweitkonto:"; cat "$W/frau.log" | head -120
    echo "--- Zweitkonto-Journal (ohne MESA/Portal):"; grep -vE "MESA|portal|Theme parsing" "$W/frau-journal.log" | tail -120
    echo "--- Sitzungsprotokoll (Ausgabe der Shell):"
    $SSH "$R sh -c 'tail -150 ~frau/.local/share/sddm/wayland-session.log 2>&1; ls -la ~frau/.local/share/sddm 2>&1'" 2>&1 | grep -vE "MESA|portal" | tail -150
    echo "--- KWin-Fenster (Zweitkonto):"
    cat > "$W/kwin-frau.sh" <<'SH'
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
id=$(gdbus call --session --dest org.kde.KWin --object-path /Scripting --method org.kde.kwin.Scripting.loadScript /tmp/dump.js mmf | grep -o "[0-9]\+" | head -1)
gdbus call --session --dest org.kde.KWin --object-path /Scripting/Script$id --method org.kde.kwin.Script.run >/dev/null
sleep 2
journalctl --user -b --no-pager 2>/dev/null | grep -o "CREATIVE-MM.*" | sort -u | head -40
SH
    scp -i "$W/key" -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$W/kwin-frau.sh" tester@127.0.0.1:/tmp/kwin-frau.sh
    $SSH "chmod 644 /tmp/dump.js /tmp/kwin-frau.sh; $R sudo -u frau sh /tmp/kwin-frau.sh; $R journalctl -b --no-pager _UID=\$(id -u frau) | grep -o 'CREATIVE-MM.*' | sort -u | head -40" 2>&1 | tail -40
    # Willkommen schließen: ist darunter der Schreibtisch?
    $SSH "$R pkill -u frau -f creative_welcome" 2>&1 | tail -1
    sleep 5
    shot desktop-frau-ohne-willkommen
    # Shell des Zweitkontos mit Protokoll neu starten: wo hängt sie?
    cat > "$W/shell-frau.sh" <<'SH'
#!/bin/sh
spid=$(pgrep -u frau -f "python3 -m creative_shell" | head -1)
echo "Shell-PID $spid"
for t in /proc/$spid/task/*; do printf '%s %s %s\n' "$(basename $t)" "$(cat $t/comm)" "$(cat $t/wchan 2>/dev/null)"; done | head -20
# Python 3.14: Stapel aller Threads im laufenden Prozess ausgeben (PEP 768)
cat > /tmp/stapel.py <<'PY'
import faulthandler, sys, threading, traceback
with open("/tmp/frau-stapel.txt", "w") as f:
    for tid, frame in sys._current_frames().items():
        f.write(f"--- Thread {tid}\n")
        traceback.print_stack(frame, file=f)
PY
chmod 644 /tmp/stapel.py
python3 -c "import sys; sys.remote_exec($spid, '/tmp/stapel.py')" && echo "remote_exec gesendet"
sleep 8
cat /tmp/frau-stapel.txt 2>&1 | tail -120
echo "--- py-spy:"
python3 -m venv /tmp/ps >/dev/null 2>&1 && /tmp/ps/bin/pip -q install py-spy >/dev/null 2>&1 && /tmp/ps/bin/py-spy dump --pid $spid 2>&1 | head -150
SH
    scp -i "$W/key" -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$W/shell-frau.sh" tester@127.0.0.1:/tmp/shell-frau.sh
    echo "--- Shell des Zweitkontos (Diagnose):"
    $SSH "$R sh /tmp/shell-frau.sh" 2>&1 | grep -v "password for" | tail -250
    $SSH "$R sh -c 'for p in \$(pgrep -u frau -f creative-shell-supervisor); do kill -CONT \$p; done'" 2>&1 | tail -1
    fshell=$($SSH "pgrep -u frau -f 'python3 -m creative_shell' | head -1")
    fwelcome=$($SSH "pgrep -u frau -f creative_welcome | head -1")
    echo "Zweitkonto: Oberfläche ${fshell:-läuft NICHT} · Willkommen ${fwelcome:+läuft (soll nicht)}"
    [ -n "$fshell" ] || fail "Zweitkonto: Die Oberfläche läuft nicht"
    [ "$haenger" = 0 ] || fail "Zweitkonto: Oberfläche hing bei $haenger von 3 Anmeldungen (schwarzer Bildschirm)"
    [ -z "$fwelcome" ] || echo "HINWEIS: Willkommen-Fenster lief beim Zweitkonto"
fi
echo "STARTTEST BESTANDEN"
kill "$(cat "$W/qemu.pid")" 2>/dev/null
exit 0
