#!/usr/bin/python3
"""Apply visual-only additions to the installed KDE lock screen."""
import sys
from pathlib import Path

START = '    // BEGIN CREATIVE LOCKSCREEN STYLE\n'
END = '    // END CREATIVE LOCKSCREEN STYLE\n'
STYLE = '''    // BEGIN CREATIVE LOCKSCREEN STYLE
    // Design aus den Einstellungen → Darstellung (Graphit dunkel / Porzellan hell)
    QtCore.Settings {
        id: creativeLook
        location: QtCore.StandardPaths.writableLocation(QtCore.StandardPaths.ConfigLocation) + "/creative-os/look.conf"
        category: "Look"
        property string design: "graphit"
        property string accent: "blau"
    }
    readonly property bool creativeLight: creativeLook.design === "porzellan"
    readonly property var creativeAccents: ({ "blau": ["#8fb3ff", "#3d6fe0"], "gruen": ["#6fdcc0", "#1f9e7f"],
                                              "orange": ["#ffb07a", "#d9773a"], "lila": ["#c3a6ff", "#7c4ddb"] })
    Kirigami.Theme.textColor: creativeLight ? "#1c2433" : "#dce6ff"
    Kirigami.Theme.backgroundColor: creativeLight ? "#ffffff" : "#1c2029"
    Kirigami.Theme.highlightColor: (creativeAccents[creativeLook.accent] || creativeAccents["blau"])[creativeLight ? 1 : 0]
    Kirigami.Theme.highlightedTextColor: creativeLight ? "#ffffff" : "#12151b"
    Kirigami.Theme.negativeTextColor: creativeLight ? "#d23c45" : "#ff8a8e"

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        text: "Creative OS · gesperrt"
        color: creativeLight ? "#46506a" : "#bac6df"
        font.family: "Arial"
        font.pixelSize: 13
    }
    // END CREATIVE LOCKSCREEN STYLE
'''


def style(text):
    if START in text:
        start = text.index(START)
        end = text.index(END, start) + len(END)
        text = text[:start] + text[end:]
    lines = text.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.strip() == 'Kirigami.Theme.colorSet: Kirigami.Theme.Complementary']
    if len(matches) != 1:
        raise ValueError('KDE-Sperrbildschirm hat eine unbekannte Struktur; keine Änderung vorgenommen.')
    lines.insert(matches[0] + 1, STYLE)
    text = ''.join(lines)
    if "import QtCore as QtCore" not in text:   # für die Design-Einstellung (Settings, StandardPaths)
        first = text.index("import ")
        text = text[:first] + "import QtCore as QtCore\n" + text[first:]
    return text


if __name__ == '__main__':
    path = Path(sys.argv[1])
    original = path.read_text()
    updated = style(original)
    backup = path.with_name(path.name + '.creative-original')
    if not backup.exists():
        backup.write_text(original)
    path.write_text(updated)
