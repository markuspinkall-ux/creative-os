"""Test a standalone GRUB menu in disposable UEFI guests, without an OS image."""

import json
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path


THEME = """
desktop-color: "#171925"
title-text: "Creative OS"
title-color: "#edf0fb"
title-font: "Unifont Regular 16"
+ label {
  left = 15%
  top = 25%
  width = 70%
  align = "left"
  text = "STARTAUSWAHL   |   ABBILDER"
  color = "#b8adff"
  font = "Unifont Regular 16"
}
+ boot_menu {
  left = 15%
  top = 34%
  width = 70%
  height = 37%
  item_color = "#edf0fb"
  selected_item_color = "#b8adff"
  item_font = "Unifont Regular 16"
  selected_item_font = "Unifont Regular 16"
  item_height = 32
  item_spacing = 8
}
+ progress_bar {
  id = "__timeout__"
  left = 15%
  top = 78%
  width = 70%
  height = 26
  fg_color = "#7765d0"
  bg_color = "#343951"
  border_color = "#7765d0"
  text_color = "#edf0fb"
  font = "Unifont Regular 16"
  text = "Automatischer Start in %d s"
}
+ label {
  left = 15%
  top = 87%
  width = 70%
  align = "left"
  text = "Pfeiltasten: Auswahl   |   Enter: Start"
  color = "#edf0fb"
  font = "Unifont Regular 16"
}
"""

CONFIG = """
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
set color_normal=light-gray/black
set menu_color_normal=light-gray/black
set menu_color_highlight=white/dark-gray
if [ -f (memdisk)/boot/grub/creative-theme.txt ]; then
    if loadfont (memdisk)/boot/grub/fonts/unicode.pf2; then
        set gfxmode=800x600,auto
        insmod all_video
        insmod gfxterm
        insmod gfxmenu
        if terminal_output gfxterm serial; then
            set theme=(memdisk)/boot/grub/creative-theme.txt
            export theme
            echo CREATIVE_THEME_READY
        fi
    fi
fi
set timeout_style=menu
set timeout=5
set default=0
echo CREATIVE_MENU_READY
menuentry 'Creative OS - Standardabbild (Test)' {
    echo CREATIVE_DEFAULT_STARTED
    sleep 2
    halt
}
menuentry 'Creative OS - Vorheriges Abbild (Test)' {
    echo CREATIVE_PREVIOUS_STARTED
    sleep 2
    halt
}
"""


def run(*args):
    subprocess.run(args, check=True)


def build_disk(folder, theme):
    folder.mkdir()
    config = folder / "grub.cfg"
    config.write_text(CONFIG)
    theme_file = folder / "theme.txt"
    theme_file.write_text(THEME)
    loader = folder / "BOOTX64.EFI"
    files = [f"boot/grub/grub.cfg={config}"]
    if theme:
        files.append(f"boot/grub/creative-theme.txt={theme_file}")
    run("grub-mkstandalone", "-O", "x86_64-efi", "--fonts=unicode", "--locales=",
        "-o", str(loader), *files)
    disk = folder / "uefi.img"
    with disk.open("wb") as output:
        output.truncate(64 * 1024 * 1024)
    run("mformat", "-i", str(disk), "::")
    run("mmd", "-i", str(disk), "::/EFI", "::/EFI/BOOT")
    run("mcopy", "-i", str(disk), str(loader), "::/EFI/BOOT/BOOTX64.EFI")
    return disk


def await_text(log, marker, vm, seconds=45):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        data = log.read_bytes() if log.exists() else b""
        if marker in data:
            return data
        if vm.poll() is not None:
            break
        time.sleep(0.05)
    raise RuntimeError(f"{log.name}: {marker.decode()} fehlt")


class Qmp:
    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(5)
        self.socket.connect(str(path))
        self.stream = self.socket.makefile("rwb")
        json.loads(self.stream.readline())
        self.command("qmp_capabilities")

    def command(self, name, **arguments):
        self.stream.write(json.dumps({"execute": name, "arguments": arguments}).encode() + b"\n")
        self.stream.flush()
        while True:
            response = json.loads(self.stream.readline())
            if "error" in response:
                raise RuntimeError(response["error"])
            if "return" in response:
                return response["return"]

    def close(self):
        self.stream.close()
        self.socket.close()


def check(case, firmware, disk, work, results, manual=False, theme=True):
    serial = results / f"{case}.log"
    qmp_path = work / "qmp.sock"
    with (results / f"{case}-qemu.log").open("wb") as qemu_log:
        vm = subprocess.Popen([
            "qemu-system-x86_64", "-machine", "q35,accel=tcg", "-m", "384",
            "-bios", str(firmware), "-drive", f"format=raw,file={disk}",
            "-net", "none", "-display", "none", "-serial", f"file:{serial}",
            "-qmp", f"unix:{qmp_path},server=on,wait=off",
        ], stdout=qemu_log, stderr=subprocess.STDOUT)
        try:
            log = await_text(serial, b"CREATIVE_MENU_READY", vm)
            start = time.monotonic()
            assert (b"CREATIVE_THEME_READY" in log) == theme, f"{case}: falscher Grafikmodus"
            qmp = Qmp(qmp_path)
            try:
                screenshot = results / f"{case}.ppm"
                deadline = time.monotonic() + 2.5
                while True:
                    qmp.command("screendump", filename=str(screenshot))
                    picture = screenshot.read_bytes()
                    if not theme or picture.count(bytes.fromhex("171925")) > 20000:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f"{case}: Creative-Theme ist im VM-Bild nicht sichtbar")
                    time.sleep(0.08)
                if manual:
                    qmp.command("human-monitor-command", **{"command-line": "sendkey down"})
                    time.sleep(5.5)
                    log = serial.read_bytes()
                    assert b"CREATIVE_DEFAULT_STARTED" not in log and b"CREATIVE_PREVIOUS_STARTED" not in log, (
                        f"{case}: Countdown wurde durch Pfeiltaste nicht gestoppt"
                    )
                    qmp.command("human-monitor-command", **{"command-line": "sendkey ret"})
                    await_text(serial, b"CREATIVE_PREVIOUS_STARTED", vm, 6)
                else:
                    await_text(serial, b"CREATIVE_DEFAULT_STARTED", vm, 10)
                    elapsed = time.monotonic() - start
                    assert 4.5 <= elapsed <= 9, f"{case}: unerwarteter Countdown ({elapsed:.2f} s)"
                if not theme:
                    assert b"Vorheriges Abbild (Test)" in serial.read_bytes(), "Textmenue-Eintrag fehlt"
                print(f"{case}: bestanden", flush=True)
            finally:
                qmp.close()
        finally:
            if vm.poll() is None:
                vm.terminate()
                try:
                    vm.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    vm.kill()
                    vm.wait()
            qmp_path.unlink(missing_ok=True)


def main():
    for tool in ("qemu-system-x86_64", "grub-mkstandalone", "mformat"):
        if not shutil.which(tool):
            raise SystemExit(f"Testwerkzeug fehlt: {tool}")
    firmware = next(Path("/usr/share/OVMF").glob("OVMF_CODE_4M.fd"))
    results = Path("grub-test-results").resolve()
    results.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="creative-grub-test-") as folder:
        work = Path(folder)
        graphical = build_disk(work / "graphic", theme=True)
        fallback = build_disk(work / "text", theme=False)
        check("01-countdown", firmware, graphical, work, results)
        check("02-manuelle-auswahl", firmware, graphical, work, results, manual=True)
        check("03-textmodus", firmware, fallback, work, results, manual=True, theme=False)


if __name__ == "__main__":
    main()
