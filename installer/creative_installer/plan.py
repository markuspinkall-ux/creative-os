"""Creative-Installation: reine Logik ohne Oberfläche (testbar ohne Qt und ohne root).

- Festplatten aus ``lsblk --json`` aufbereiten (welche dürfen gewählt werden?)
- Benutzername aus dem vollen Namen vorschlagen
- Eingaben prüfen
- Kickstart-Datei für Anaconda erzeugen (ganze Platte, Btrfs, Creative OS aus dem
  Abbild auf dem USB-Stick, danach Updates aus der GitHub-Registry)
"""

import json
import re
import unicodedata

MIN_BYTES = 40 * 1000 ** 3          # unter 40 GB passt Creative OS nicht sinnvoll drauf
IMAGE_REPO = "ghcr.io/markuspinkall-ux/creative-os"
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
DISK_RE = re.compile(r"^/dev/(sd[a-z]+|nvme\d+n\d+|vd[a-z]+|mmcblk\d+|xvd[a-z]+)$")
RESERVED_USERS = {"root", "bin", "daemon", "adm", "lp", "sync", "shutdown", "halt", "mail",
                  "operator", "games", "ftp", "nobody", "liveuser", "sddm", "wheel"}

KEYBOARDS = {  # Anzeige → (vconsole, X11-Layout)
    "Deutsch": ("de-nodeadkeys", "de(nodeadkeys)"),
    "Deutsch (Schweiz)": ("ch-de_nodeadkeys", "ch(de_nodeadkeys)"),
    "Österreich": ("de-nodeadkeys", "at(nodeadkeys)"),
    "Englisch (USA)": ("us", "us"),
    "Englisch (UK)": ("gb", "gb"),
}

FS_NAMES = {"ntfs": "Windows", "BitLocker": "Windows (BitLocker)", "vfat": "FAT", "exfat": "exFAT",
            "ext4": "Linux", "btrfs": "Linux", "xfs": "Linux", "crypto_LUKS": "verschlüsselt",
            "swap": "Linux", "LVM2_member": "Linux", "apfs": "macOS", "hfsplus": "macOS"}


def human_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB", "MB") or n >= 100 else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1000
    return f"{n:.0f} TB"


def _previous(dev):
    """Was liegt bisher auf der Platte? (für den Hinweis „bisher: Windows“)"""
    found, labels = [], []
    for part in dev.get("children") or []:
        fs = part.get("fstype") or ""
        name = FS_NAMES.get(fs)
        if name and name not in found and fs not in ("vfat", "swap"):
            found.append(name)
        label = (part.get("label") or "").strip()
        if label and label not in labels and label.upper() not in ("EFI", "SYSTEM", "BOOT", "RECOVERY", "WINRE_DRV"):
            labels.append(label)
    if not dev.get("children"):
        fs = dev.get("fstype") or ""
        if FS_NAMES.get(fs):
            found.append(FS_NAMES[fs])
    if not found and not labels:
        return "leer"
    text = " + ".join(found) if found else "Daten"
    if labels:
        text += " (" + ", ".join(labels[:2]) + ")"
    return text


def parse_disks(lsblk_json, live_disks=()):
    """Liste der Festplatten für die Auswahl.

    ``live_disks``: Geräte, von denen gerade gestartet wurde (der USB-Stick) – nie wählbar.
    """
    data = json.loads(lsblk_json) if isinstance(lsblk_json, str) else lsblk_json
    disks = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        name = (dev.get("name") or "").removeprefix("/dev/")
        path = dev.get("path") or "/dev/" + name
        if name.startswith(("loop", "zram", "sr", "ram")):
            continue
        size = int(dev.get("size") or 0)
        model = " ".join((dev.get("model") or "").split()) or "Festplatte"
        tran = (dev.get("tran") or "").lower()
        removable = bool(dev.get("rm")) or tran == "usb"
        kind = {"nvme": "NVMe-SSD", "sata": "SATA", "usb": "USB", "virtio": "virtuell"}.get(tran, tran.upper() or "Festplatte")
        if name.startswith("nvme"):
            kind = "NVMe-SSD"
        elif name.startswith("vd"):
            kind = "virtuell"
        reason = ""
        if path in live_disks:
            reason = "Von diesem Stick läuft gerade die Installation"
        elif size < MIN_BYTES:
            reason = f"Zu klein (mindestens {human_size(MIN_BYTES)})"
        elif dev.get("ro"):
            reason = "Schreibgeschützt"
        disks.append({
            "path": path,
            "name": name,
            "model": model,
            "size": size,
            "sizeText": human_size(size),
            "kind": kind,
            "removable": removable,
            "previous": _previous(dev),
            "eligible": not reason,
            "reason": reason,
        })
    disks.sort(key=lambda d: (not d["eligible"], d["removable"], d["name"]))
    return disks


def suggest_username(full_name):
    first = (full_name or "").strip().split(" ")[0] if (full_name or "").strip() else ""
    text = first.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9_-]", "", text)
    if text and not re.match(r"[a-z_]", text[0]):
        text = "u" + text
    text = text[:32]
    if text in RESERVED_USERS:
        text += "1"
    return text


def password_strength(pw):
    """0 = leer, 1 = schwach, 2 = mittel, 3 = gut"""
    if not pw:
        return 0
    score = 0
    score += len(pw) >= 8
    score += len(pw) >= 12
    score += bool(re.search(r"[A-Z]", pw) and re.search(r"[a-z]", pw))
    score += bool(re.search(r"[0-9]", pw))
    score += bool(re.search(r"[^A-Za-z0-9]", pw))
    return 1 if score <= 2 else (2 if score <= 3 else 3)


def validate(cfg, disks=None):
    """Gibt eine verständliche Fehlermeldung zurück oder "" wenn alles passt."""
    disk = cfg.get("disk", "")
    if not DISK_RE.match(disk or ""):
        return "Bitte eine Festplatte auswählen."
    if disks is not None:
        match = next((d for d in disks if d["path"] == disk), None)
        if match is None:
            return "Die gewählte Festplatte ist nicht mehr vorhanden."
        if not match["eligible"]:
            return match["reason"]
    if not (cfg.get("fullName") or "").strip():
        return "Bitte deinen Namen eintragen."
    if any(c in cfg["fullName"] for c in ':\n"\\'):
        return "Der Name darf keine Doppelpunkte, Anführungszeichen oder Zeilenumbrüche enthalten."
    user = cfg.get("userName", "")
    if not USERNAME_RE.match(user or ""):
        return "Der Benutzername darf nur Kleinbuchstaben, Ziffern, - und _ enthalten und muss mit einem Buchstaben beginnen."
    if user in RESERVED_USERS:
        return f"Der Benutzername „{user}“ ist reserviert."
    pw = cfg.get("password", "")
    if len(pw) < 6:
        return "Das Passwort muss mindestens 6 Zeichen haben."
    if pw != cfg.get("password2", pw):
        return "Die Passwörter stimmen nicht überein."
    host = cfg.get("hostName", "creative-os")
    if not HOSTNAME_RE.match(host or ""):
        return "Der Computername darf nur Buchstaben, Ziffern und - enthalten."
    if cfg.get("keyboard", "Deutsch") not in KEYBOARDS:
        return "Unbekannte Tastaturbelegung."
    if cfg.get("variant", "amd") not in ("amd", "nvidia"):
        return "Unbekannte Variante."
    return ""


def kickstart(cfg, password_hash, source_ref=None):
    """Kickstart für Anaconda. ``password_hash``: SHA-512-crypt (vom Helfer mit openssl erzeugt)."""
    variant = cfg.get("variant", "amd")
    target = f"{IMAGE_REPO}:{variant}"
    source = source_ref or target
    disk = cfg["disk"].removeprefix("/dev/")
    vc, xl = KEYBOARDS[cfg.get("keyboard", "Deutsch")]
    gecos = cfg["fullName"].strip()
    return f"""# Creative OS – automatisch erzeugt von der Creative-Installation
lang de_DE.UTF-8
keyboard --vckeymap={vc} --xlayouts='{xl}'
timezone {cfg.get("timezone", "Europe/Berlin")} --utc
network --bootproto=dhcp --activate --hostname={cfg.get("hostName", "creative-os")}
ignoredisk --only-use={disk}
zerombr
clearpart --all --initlabel --drives={disk}
autopart --type=btrfs --noswap
bootloader --boot-drive={disk}
rootpw --lock
user --name={cfg["userName"]} --gecos="{gecos}" --groups=wheel --iscrypted --password={password_hash}
# Creative OS kommt vom Stick (ohne Internet) …
ostreecontainer --url={source} --transport=containers-storage --no-signature-verification

%post --erroronfail --log=/root/creative-install-post.log
# … und holt sich Updates danach direkt aus der GitHub-Registry
bootc switch --mutate-in-place --transport registry {target} || rpm-ostree rebase --experimental ostree-unverified-registry:{target} || true
%end

%post --nochroot --log=/mnt/sysroot/root/creative-install-efi.log
# Secure Boot: Schlüssel der Creative-OS-Treiber zur Freischaltung vormerken (Passwort: creative)
if [ -d /sys/firmware/efi ] && mokutil --sb-state 2>/dev/null | grep -qi enabled; then
    key=/usr/share/creative-os/secureboot/creative-os-mok.der   # die Live-Umgebung ist Creative OS selbst
    [ -f "$key" ] && printf 'creative\\ncreative\\n' | mokutil --import "$key" || true
fi
# Eintrag im Startmenü des PCs: „Creative OS“ statt „Fedora“
if [ -d /sys/firmware/efi ] && command -v efibootmgr >/dev/null 2>&1; then
    num=$(efibootmgr 2>/dev/null | grep -E '^Boot[0-9A-F]{{4}}\\*? +Fedora' | head -1 | sed -E 's/^Boot([0-9A-F]{{4}}).*/\\1/')
    part=$(lsblk -lnpo NAME,PARTTYPE /dev/{disk} | awk 'tolower($2)=="c12a7328-f81f-11d2-ba4b-00a0c93ec93b"{{print $1; exit}}')
    pnum=$(cat "/sys/class/block/$(basename "$part")/partition" 2>/dev/null)
    if [ -n "$num" ] && [ -n "$pnum" ] && efibootmgr -q -c -d /dev/{disk} -p "$pnum" -L "Creative OS" -l '\\EFI\\fedora\\shimx64.efi'; then
        efibootmgr -q -b "$num" -B || true
    fi
fi
%end
"""


# Fortschritt aus den Zeilen von „anaconda --cmdline“ ablesen: (Schlüsselwort, Prozent, Text)
STAGES = [
    ("Starting installer", 2, "Installation wird vorbereitet"),
    ("Checking storage", 4, "Festplatte wird geprüft"),
    ("Configuring storage", 6, "Festplatte wird eingerichtet"),
    ("Creating disklabel", 7, "Festplatte wird eingerichtet"),
    ("Creating btrfs", 9, "Dateisystem wird angelegt"),
    ("Creating efi", 9, "Startpartition wird angelegt"),
    ("Running pre-installation", 11, "Installation wird vorbereitet"),
    ("Starting package installation", 12, "Creative OS wird kopiert"),
    ("Deployment starting", 14, "Creative OS wird kopiert"),
    ("Pulling", 20, "Creative OS wird kopiert"),
    ("Importing", 40, "Creative OS wird kopiert"),
    ("Writing objects", 60, "Creative OS wird kopiert"),
    ("Deployment complete", 75, "Creative OS ist kopiert"),
    ("Configuring installed system", 78, "System wird eingerichtet"),
    ("Creating users", 82, "Dein Benutzerkonto wird angelegt"),
    ("Installing boot loader", 86, "Startmenü wird eingerichtet"),
    ("Performing post-installation", 90, "Letzte Schritte"),
    ("Running post-installation", 92, "Letzte Schritte"),
    ("Storing configuration", 96, "Einstellungen werden gespeichert"),
    ("Installation complete", 100, "Fertig"),
]


def stage_for(line, current=0):
    """Neuer (Prozent, Text) für eine Ausgabezeile – oder None. Geht nie rückwärts."""
    for key, pct, text in STAGES:
        if key.lower() in line.lower() and pct >= current:
            return pct, text
    return None
