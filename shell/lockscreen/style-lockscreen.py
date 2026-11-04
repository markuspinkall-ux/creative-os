#!/usr/bin/python3
"""Apply visual-only additions to the installed KDE lock screen."""
import sys
from pathlib import Path

START = '    // BEGIN CREATIVE LOCKSCREEN STYLE\n'
END = '    // END CREATIVE LOCKSCREEN STYLE\n'
STYLE = '''    // BEGIN CREATIVE LOCKSCREEN STYLE
    Kirigami.Theme.textColor: "#dce6ff"
    Kirigami.Theme.backgroundColor: "#1c2029"
    Kirigami.Theme.highlightColor: "#8fb3ff"
    Kirigami.Theme.highlightedTextColor: "#12151b"
    Kirigami.Theme.negativeTextColor: "#ff8a8e"

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        text: "Creative OS · gesperrt"
        color: "#bac6df"
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
    return ''.join(lines)


if __name__ == '__main__':
    path = Path(sys.argv[1])
    original = path.read_text()
    updated = style(original)
    backup = path.with_name(path.name + '.creative-original')
    if not backup.exists():
        backup.write_text(original)
    path.write_text(updated)
