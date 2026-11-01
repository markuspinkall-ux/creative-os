import QtQuick
import Creative

// Kalender im Schnellzugriff: Monat blättern, heute hervorgehoben,
// bundesweite Feiertage mit Punkt markiert.
Item {
    id: cal

    property date today: new Date()
    property int year: today.getFullYear()
    property int month: today.getMonth()          // 0 = Januar
    property var picked: null                     // gewählter Tag (Date)

    readonly property var monthNames: ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
                                       "August", "September", "Oktober", "November", "Dezember"]
    readonly property var dayNames: ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"]

    function reset() {
        today = new Date()
        year = today.getFullYear()
        month = today.getMonth()
        picked = null
    }
    function step(d) {
        let m = month + d, y = year
        if (m < 0) { m = 11; y-- }
        if (m > 11) { m = 0; y++ }
        month = m; year = y
    }
    function sameDay(a, b) {
        return a && b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
    }
    function key(d) { return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate() }

    // Bundesweite Feiertage (Ostern nach Gauß/Anonymous-Algorithmus)
    function holidays(y) {
        const a = y % 19, b = Math.floor(y / 100), c = y % 100, d = Math.floor(b / 4), e = b % 4
        const f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3)
        const h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4
        const l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451)
        const em = Math.floor((h + l - 7 * m + 114) / 31) - 1, ed = ((h + l - 7 * m + 114) % 31) + 1
        const easter = new Date(y, em, ed)
        const rel = (n) => { const x = new Date(easter); x.setDate(x.getDate() + n); return x }
        const list = [
            [new Date(y, 0, 1), "Neujahr"], [rel(-2), "Karfreitag"], [rel(1), "Ostermontag"],
            [new Date(y, 4, 1), "Tag der Arbeit"], [rel(39), "Christi Himmelfahrt"], [rel(50), "Pfingstmontag"],
            [new Date(y, 9, 3), "Tag der Deutschen Einheit"], [new Date(y, 11, 25), "1. Weihnachtstag"],
            [new Date(y, 11, 26), "2. Weihnachtstag"]
        ]
        const map = {}
        for (const [dt, name] of list) map[key(dt)] = name
        return map
    }
    readonly property var holidayMap: holidays(year)

    // 42 Felder, Woche beginnt am Montag
    readonly property var cells: {
        const first = new Date(year, month, 1)
        const offset = (first.getDay() + 6) % 7
        const out = []
        for (let n = 0; n < 42; n++)
            out.push(new Date(year, month, 1 - offset + n))
        return out
    }

    implicitHeight: col.implicitHeight

    Column {
        id: col
        width: parent.width
        spacing: 10

        // Heute groß
        Column {
            spacing: 2
            Text {
                text: cal.dayNames[cal.today.getDay()] + ", " + cal.today.getDate() + ". " + cal.monthNames[cal.today.getMonth()]
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 15
                font.bold: true
            }
            Text {
                readonly property string h: cal.holidays(cal.today.getFullYear())[cal.key(cal.today)] || ""
                visible: h.length > 0
                text: "Heute: " + h
                color: Theme.flame
                font.family: Theme.fontFamily
                font.pixelSize: 12
            }
        }

        // Monat + Blättern
        Item {
            width: parent.width
            height: 32
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: cal.monthNames[cal.month] + " " + cal.year
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: 14
                font.bold: true
            }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Rectangle {
                    visible: cal.year !== cal.today.getFullYear() || cal.month !== cal.today.getMonth()
                    width: todayText.implicitWidth + 18
                    height: 28
                    radius: 8
                    color: tm.containsMouse ? Theme.hover : Qt.rgba(1, 1, 1, 0.06)
                    Text { id: todayText; anchors.centerIn: parent; text: "Heute"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 12; font.bold: true }
                    MouseArea { id: tm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: cal.reset() }
                }
                IconButton { width: 28; height: 28; icon: "back"; iconSize: 14; label: "Voriger Monat"; onClicked: cal.step(-1) }
                IconButton { width: 28; height: 28; icon: "forward"; iconSize: 14; label: "Nächster Monat"; onClicked: cal.step(1) }
            }
        }

        // Wochentage
        Row {
            Repeater {
                model: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
                delegate: Text {
                    width: col.width / 7
                    horizontalAlignment: Text.AlignHCenter
                    text: modelData
                    color: index >= 5 ? Theme.textMuted : Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }

        // Tage
        Grid {
            columns: 7
            Repeater {
                model: cal.cells
                delegate: Item {
                    readonly property bool inMonth: modelData.getMonth() === cal.month
                    readonly property bool isToday: cal.sameDay(modelData, cal.today)
                    readonly property bool isPicked: cal.sameDay(modelData, cal.picked)
                    readonly property string holiday: inMonth ? (cal.holidayMap[cal.key(modelData)] || "") : ""
                    width: col.width / 7
                    height: 36
                    Rectangle {
                        anchors.centerIn: parent
                        width: 32; height: 32; radius: 16
                        color: isToday ? Theme.accent
                               : (isPicked ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.22)
                                           : (dm.containsMouse ? Theme.hover : "transparent"))
                    }
                    Text {
                        anchors.centerIn: parent
                        text: modelData.getDate()
                        color: isToday ? Theme.accentText : Theme.text
                        opacity: inMonth ? ((index % 7) >= 5 && !isToday ? 0.7 : 1) : 0.3
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.bold: isToday || isPicked
                    }
                    Rectangle {
                        visible: holiday.length > 0
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 3
                        width: 4; height: 4; radius: 2
                        color: isToday ? Theme.accentText : Theme.flame
                    }
                    MouseArea {
                        id: dm
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!inMonth) { cal.year = modelData.getFullYear(); cal.month = modelData.getMonth() }
                            cal.picked = modelData
                        }
                    }
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.getDate() + ". " + cal.monthNames[modelData.getMonth()] + (holiday ? ", " + holiday : "")
                }
            }
        }

        // Gewählter Tag
        Text {
            readonly property string h: cal.picked ? (cal.holidays(cal.picked.getFullYear())[cal.key(cal.picked)] || "") : ""
            visible: cal.picked !== null
            width: parent.width
            wrapMode: Text.WordWrap
            text: cal.picked ? cal.dayNames[cal.picked.getDay()] + ", " + cal.picked.getDate() + ". "
                               + cal.monthNames[cal.picked.getMonth()] + " " + cal.picked.getFullYear()
                               + (h ? " · " + h : "") : ""
            color: h ? Theme.flame : Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: 12
        }
    }
}
