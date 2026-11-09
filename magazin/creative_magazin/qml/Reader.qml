import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Creative

// Ein Artikel in voller Länge – mit Quellenangabe am Ende.
Rectangle {
    id: reader

    required property QtObject magazine
    property var order: []

    readonly property var article: magazine.reader
    readonly property bool open: !!article.id
    readonly property string shownId: article.id || ""
    readonly property int position: open ? order.indexOf(article.id) : -1
    readonly property bool loading: !!article.loading
    readonly property var blocks: article.blocks || []

    visible: open
    color: Theme.ground

    function step(delta) {
        const index = position + delta
        if (position >= 0 && index >= 0 && index < order.length)
            magazine.openArticle(order[index])
    }

    function scroll(delta) {
        flick.contentY = Math.max(0, Math.min(flick.contentY + delta, flick.contentHeight - flick.height))
    }

    onShownIdChanged: flick.contentY = 0

    component Hint: Label {
        color: Theme.textMuted
        font.pixelSize: 13
        elide: Text.ElideRight
        textFormat: Text.PlainText
    }

    Shortcut { sequence: "Escape"; enabled: reader.open; onActivated: reader.magazine.closeArticle() }
    Shortcut { sequence: "Right"; enabled: reader.open; onActivated: reader.step(1) }
    Shortcut { sequence: "Left"; enabled: reader.open; onActivated: reader.step(-1) }
    Shortcut { sequence: "Down"; enabled: reader.open; onActivated: reader.scroll(80) }
    Shortcut { sequence: "Up"; enabled: reader.open; onActivated: reader.scroll(-80) }
    Shortcut { sequences: ["PgDown", "Space"]; enabled: reader.open; onActivated: reader.scroll(flick.height - 80) }
    Shortcut { sequence: "PgUp"; enabled: reader.open; onActivated: reader.scroll(-(flick.height - 80)) }
    Shortcut { sequence: "Home"; enabled: reader.open; onActivated: flick.contentY = 0 }

    // Klicks und Mausrad gehen nicht an das Heft darunter.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onWheel: wheel => wheel.accepted = true
    }

    // ------------------------------------------------------------ Leiste oben
    RowLayout {
        id: toolbar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 20
        spacing: 10
        CButton {
            text: "‹  Zurück zum Heft"
            onClicked: reader.magazine.closeArticle()
        }
        Hint {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: reader.position >= 0 ? "Artikel " + (reader.position + 1) + " von " + reader.order.length : ""
        }
        CButton {
            text: reader.article.saved ? "★ Gemerkt" : "☆ Merken"
            primary: !!reader.article.saved
            onClicked: reader.magazine.toggleSaved(reader.shownId)
        }
        CButton {
            text: "Original öffnen"
            onClicked: reader.magazine.openOriginal(reader.article.link || "")
        }
    }

    Flickable {
        id: flick
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: toolbar.bottom
        anchors.bottom: parent.bottom
        anchors.topMargin: 10
        contentWidth: width
        contentHeight: column.implicitHeight + 80
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        ColumnLayout {
            id: column
            width: Math.min(flick.width - 64, 780)
            x: (flick.width - width) / 2
            y: 20
            spacing: 16

            Label {
                Layout.fillWidth: true
                text: ((reader.article.rubric || "") + "  ·  " + (reader.article.site || "")).toUpperCase()
                color: Theme.flame
                font.pixelSize: 12
                font.bold: true
                font.letterSpacing: 1.5
                elide: Text.ElideRight
            }
            Label {
                Layout.fillWidth: true
                text: reader.article.title || ""
                color: Theme.text
                font.pixelSize: 34
                font.bold: true
                wrapMode: Text.WordWrap
                textFormat: Text.PlainText
            }
            Hint {
                Layout.fillWidth: true
                text: [reader.article.author ? "Von " + reader.article.author : "", reader.article.date || ""]
                      .filter(part => part.length > 0).join("  ·  ")
            }
            Rectangle {
                implicitWidth: 70
                implicitHeight: 3
                color: Theme.flame
            }

            Image {
                id: hero
                Layout.fillWidth: true
                Layout.preferredHeight: status === Image.Ready ? column.width * implicitHeight / Math.max(1, implicitWidth) : 0
                visible: status === Image.Ready
                source: reader.article.image || ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                sourceSize.width: 1600
            }

            // Anriss, solange der Volltext lädt oder wenn die Seite keinen hergibt.
            Label {
                Layout.fillWidth: true
                visible: text.length > 0 && (reader.loading || reader.blocks.length === 0)
                text: reader.article.summary || ""
                color: Theme.text
                font.pixelSize: 18
                font.italic: true
                wrapMode: Text.WordWrap
                textFormat: Text.PlainText
                lineHeight: 1.3
            }
            Hint {
                visible: reader.loading
                text: "Artikel wird geladen …"
            }

            Repeater {
                model: reader.blocks
                delegate: ColumnLayout {
                    id: block
                    required property var modelData
                    readonly property string type: modelData.type || "p"
                    Layout.fillWidth: true
                    Layout.topMargin: type === "h" ? 10 : 0
                    spacing: 6

                    Image {
                        id: picture
                        Layout.fillWidth: true
                        Layout.preferredHeight: visible ? column.width * implicitHeight / Math.max(1, implicitWidth) : 0
                        visible: block.type === "img" && status === Image.Ready
                        source: block.type === "img" ? (block.modelData.src || "") : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        sourceSize.width: 1600
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: text.length > 0 && (block.type !== "img" || picture.status === Image.Ready)
                        text: block.type === "li" ? "•  " + (block.modelData.text || "") : (block.modelData.text || "")
                        color: block.type === "img" ? Theme.textMuted : Theme.text
                        font.pixelSize: block.type === "h" ? 22 : (block.type === "img" ? 12 : 17)
                        font.bold: block.type === "h"
                        font.italic: block.type === "quote"
                        leftPadding: block.type === "quote" || block.type === "li" ? 18 : 0
                        lineHeight: block.type === "p" || block.type === "quote" ? 1.35 : 1.0
                        wrapMode: Text.WordWrap
                        textFormat: Text.PlainText
                        background: Item {
                            Rectangle {
                                visible: block.type === "quote"
                                width: 3
                                height: parent.height
                                color: Theme.accent
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: 6
                visible: !reader.loading && (!!reader.article.error || !!reader.article.short)
                implicitHeight: notice.implicitHeight + 28
                color: Theme.surface
                radius: Theme.radiusRow
                Label {
                    id: notice
                    anchors.fill: parent
                    anchors.margins: 14
                    text: reader.article.error
                          || "Hier steht nur ein Teil des Artikels – zum Beispiel, weil die Seite ihn hinter einer Bezahlschranke zeigt. Den vollständigen Text liest du im Original."
                    color: Theme.text
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    textFormat: Text.PlainText
                }
            }

            // ------------------------------------------------------------ Quelle
            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: 20
                implicitHeight: sourceInfo.implicitHeight + 32
                color: Theme.surface
                radius: Theme.radiusMenu
                border.color: Theme.hairline

                ColumnLayout {
                    id: sourceInfo
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 6
                    Label {
                        text: "QUELLE"
                        color: Theme.flame
                        font.pixelSize: 12
                        font.bold: true
                        font.letterSpacing: 2
                    }
                    Label {
                        Layout.fillWidth: true
                        text: reader.article.site || ""
                        color: Theme.text
                        font.pixelSize: 17
                        font.bold: true
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }
                    Hint {
                        Layout.fillWidth: true
                        text: [reader.article.author ? "Autor: " + reader.article.author : "",
                               reader.article.date ? "Veröffentlicht: " + reader.article.date : ""]
                              .filter(part => part.length > 0).join("  ·  ")
                    }
                    Hint {
                        Layout.fillWidth: true
                        text: reader.article.link || ""
                        elide: Text.ElideMiddle
                    }
                    RowLayout {
                        Layout.topMargin: 6
                        spacing: 10
                        CButton {
                            text: "Original öffnen"
                            primary: true
                            onClicked: reader.magazine.openOriginal(reader.article.link || "")
                        }
                        CButton {
                            text: "Zur Seite " + (reader.article.site || "")
                            onClicked: reader.magazine.openOriginal(reader.article.home || "")
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 10
                CButton {
                    text: "‹  Vorheriger Artikel"
                    enabled: reader.position > 0
                    onClicked: reader.step(-1)
                }
                Item { Layout.fillWidth: true }
                CButton {
                    text: "Nächster Artikel  ›"
                    enabled: reader.position >= 0 && reader.position + 1 < reader.order.length
                    onClicked: reader.step(1)
                }
            }
        }
    }
}
