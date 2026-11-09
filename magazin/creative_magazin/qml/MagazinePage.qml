import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Creative

// Eine Seite des Hefts: Titelseite, Inhaltsverzeichnis oder vier Artikel einer Rubrik.
Rectangle {
    id: root

    property var info: ({ kind: "blank" })
    property int number: 0
    property var articles: []
    property string issueLabel: ""
    property var rubricOrder: []
    property bool hasSources: false
    property bool loading: false

    signal openArticle(string key)
    signal openPage(int index)
    signal rubricChosen(string key, string rubric)
    signal saveToggled(string key)
    signal originalRequested(string url)
    signal addSources()

    readonly property string kind: info && info.kind ? info.kind : "blank"
    readonly property var lead: articles.find(a => !!a.image) || articles[0] || null
    readonly property var leadItem: lead || ({})
    readonly property var more: articles.filter(a => !root.lead || a.id !== root.lead.id).slice(0, 4)
    readonly property string counts: {
        const parts = []
        for (const name of rubricOrder) {
            const count = articles.filter(a => a.rubric === name).length
            if (count > 0)
                parts.push(count + " " + name)
        }
        return parts.join("  ·  ")
    }
    readonly property var rows: {
        const result = []
        const sections = kind === "contents" && info.sections ? info.sections : []
        for (const section of sections) {
            result.push({ head: true, text: section.rubric, title: "", site: "", page: 0 })
            for (const entry of section.entries)
                result.push({ head: false, text: "", title: entry.title, site: entry.site, page: entry.page })
        }
        return result
    }

    color: Theme.surface
    radius: Theme.radiusMenu
    border.color: Theme.hairline
    opacity: kind === "blank" ? 0 : 1
    clip: true

    component Hint: Label {
        color: Theme.textMuted
        font.pixelSize: 13
        elide: Text.ElideRight
        textFormat: Text.PlainText
    }

    component Kicker: Label {
        color: Theme.flame
        font.pixelSize: 12
        font.bold: true
        font.letterSpacing: 1.5
        elide: Text.ElideRight
        textFormat: Text.PlainText
    }

    component MenuEntry: MenuItem {
        id: entry
        contentItem: Label {
            text: entry.text
            color: Theme.text
            font.pixelSize: 13
            leftPadding: 6
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            implicitWidth: 230
            implicitHeight: 34
            radius: 8
            color: entry.highlighted ? Theme.hover : "transparent"
        }
    }

    Loader {
        anchors.fill: parent
        anchors.margins: 28
        anchors.bottomMargin: root.kind === "cover" || root.kind === "empty" ? 28 : 44
        sourceComponent: root.kind === "cover" ? cover
                         : root.kind === "contents" ? contents
                         : root.kind === "teasers" ? teasers
                         : root.kind === "empty" ? empty : null
    }

    Hint {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 14
        anchors.horizontalCenter: parent.horizontalCenter
        visible: root.kind === "contents" || root.kind === "teasers"
        text: "Seite " + (root.number + 1)
        font.pixelSize: 11
    }

    // ------------------------------------------------------------ Titelseite
    Component {
        id: cover
        ColumnLayout {
            spacing: 14

            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 0
                    Label {
                        text: "CREATIVE"
                        color: Theme.accent
                        font.pixelSize: 15
                        font.bold: true
                        font.letterSpacing: 7
                    }
                    Label {
                        text: "MAGAZIN"
                        color: Theme.text
                        font.pixelSize: 48
                        font.bold: true
                        font.letterSpacing: 3
                    }
                }
                Item { Layout.fillWidth: true }
                ColumnLayout {
                    spacing: 4
                    Label {
                        Layout.alignment: Qt.AlignRight
                        text: root.issueLabel
                        color: Theme.text
                        font.pixelSize: 14
                        font.bold: true
                    }
                    Hint {
                        Layout.alignment: Qt.AlignRight
                        text: root.articles.length + " Artikel"
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 3
                color: Theme.flame
            }

            Rectangle {
                id: leadBox
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 180
                color: Theme.raised
                clip: true

                Image {
                    anchors.fill: parent
                    source: root.leadItem.image || ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    sourceSize.width: 1400
                }
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: parent.height * 0.65
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 1.0; color: "#f012151b" }
                    }
                }
                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 22
                    spacing: 6
                    Kicker {
                        Layout.fillWidth: true
                        text: ((root.leadItem.rubric || "") + "  ·  " + (root.leadItem.site || "")).toUpperCase()
                    }
                    Label {
                        Layout.fillWidth: true
                        text: root.leadItem.title || ""
                        color: Theme.text
                        font.pixelSize: 30
                        font.bold: true
                        wrapMode: Text.WordWrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                        textFormat: Text.PlainText
                    }
                    Hint {
                        Layout.fillWidth: true
                        text: root.leadItem.summary || ""
                        color: Theme.text
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (root.lead) root.openArticle(root.lead.id)
                }
            }

            Kicker {
                text: "AUSSERDEM IN DIESER AUSGABE"
                color: Theme.textMuted
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: 12
                columnSpacing: 20
                Repeater {
                    model: root.more
                    delegate: Item {
                        id: headline
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        implicitHeight: headlineText.implicitHeight
                        ColumnLayout {
                            id: headlineText
                            width: parent.width
                            spacing: 3
                            Kicker {
                                Layout.fillWidth: true
                                text: (headline.modelData.rubric || "").toUpperCase() + "  ·  " + (headline.modelData.site || "")
                                font.pixelSize: 11
                            }
                            Label {
                                Layout.fillWidth: true
                                text: headline.modelData.title || ""
                                color: headlineMouse.containsMouse ? Theme.accent : Theme.text
                                font.pixelSize: 15
                                font.bold: true
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                textFormat: Text.PlainText
                            }
                        }
                        MouseArea {
                            id: headlineMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.openArticle(headline.modelData.id)
                        }
                    }
                }
            }

            Hint {
                Layout.fillWidth: true
                text: root.counts
            }
        }
    }

    // ------------------------------------------------------------ Inhaltsverzeichnis
    Component {
        id: contents
        ColumnLayout {
            spacing: 10
            Label {
                text: "Inhalt"
                color: Theme.text
                font.pixelSize: 34
                font.bold: true
            }
            Rectangle {
                implicitWidth: 80
                implicitHeight: 3
                color: Theme.flame
            }
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 2
                model: root.rows
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    width: ListView.view.width - 10
                    height: modelData.head ? 46 : 34
                    radius: Theme.radiusRow
                    color: !row.modelData.head && rowMouse.containsMouse ? Theme.hover : "transparent"

                    Kicker {
                        anchors.left: parent.left
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: 6
                        anchors.bottomMargin: 6
                        visible: row.modelData.head
                        text: (row.modelData.text || "").toUpperCase()
                        font.pixelSize: 14
                    }
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 6
                        anchors.rightMargin: 6
                        visible: !row.modelData.head
                        spacing: 12
                        Label {
                            Layout.fillWidth: true
                            text: row.modelData.title || ""
                            color: Theme.text
                            font.pixelSize: 14
                            elide: Text.ElideRight
                            textFormat: Text.PlainText
                        }
                        Hint {
                            Layout.maximumWidth: 160
                            text: row.modelData.site || ""
                            font.pixelSize: 12
                        }
                        Label {
                            text: "S. " + (row.modelData.page + 1)
                            color: Theme.accent
                            font.pixelSize: 13
                            font.bold: true
                        }
                    }
                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        enabled: !row.modelData.head
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.openPage(row.modelData.page)
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------ Artikel einer Rubrik
    Component {
        id: teasers
        ColumnLayout {
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Kicker {
                    text: (root.info.rubric || "").toUpperCase()
                    font.pixelSize: 15
                    font.letterSpacing: 3
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 2
                    color: Theme.hairline
                }
            }
            GridLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                columns: 2
                rowSpacing: 16
                columnSpacing: 16
                Repeater {
                    model: 4
                    delegate: Item {
                        id: slot
                        required property int index
                        readonly property var article: (root.info.items || [])[index] || null
                        readonly property var a: article || ({})
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        Layout.preferredHeight: 1

                        Rectangle {
                            anchors.fill: parent
                            visible: slot.article !== null
                            color: Theme.raised
                            radius: 6
                            clip: true
                            border.color: cardMouse.containsMouse ? Theme.accent : "transparent"

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 8
                                Item {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: parent.height * 0.42
                                    visible: !!slot.a.image && picture.status !== Image.Error
                                    clip: true
                                    Image {
                                        id: picture
                                        anchors.fill: parent
                                        source: slot.a.image || ""
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        sourceSize.width: 900
                                    }
                                }
                                Kicker {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 14
                                    Layout.rightMargin: 14
                                    Layout.topMargin: slot.a.image ? 0 : 14
                                    text: (slot.a.site || "").toUpperCase()
                                    font.pixelSize: 11
                                }
                                Label {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 14
                                    Layout.rightMargin: 14
                                    text: slot.a.title || ""
                                    color: slot.a.read ? Theme.textMuted : Theme.text
                                    font.pixelSize: 18
                                    font.bold: true
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 3
                                    elide: Text.ElideRight
                                    textFormat: Text.PlainText
                                }
                                Hint {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Layout.leftMargin: 14
                                    Layout.rightMargin: 14
                                    text: slot.a.summary || ""
                                    wrapMode: Text.WordWrap
                                    verticalAlignment: Text.AlignTop
                                    maximumLineCount: slot.a.image ? 3 : 9
                                }
                                Hint {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 14
                                    Layout.rightMargin: 14
                                    Layout.bottomMargin: 12
                                    text: (slot.a.saved ? "★ Gemerkt  ·  " : "") + (slot.a.date || "")
                                    font.pixelSize: 11
                                }
                            }

                            MouseArea {
                                id: cardMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: mouse => {
                                    if (mouse.button === Qt.RightButton)
                                        cardMenu.popup()
                                    else if (slot.article)
                                        root.openArticle(slot.a.id)
                                }
                            }

                            Menu {
                                id: cardMenu
                                padding: 6
                                background: Rectangle {
                                    implicitWidth: 240
                                    color: Theme.raised
                                    radius: Theme.radiusRow
                                    border.color: Theme.hairline
                                }
                                MenuEntry {
                                    text: "Lesen"
                                    onTriggered: root.openArticle(slot.a.id)
                                }
                                MenuEntry {
                                    text: slot.a.saved ? "Nicht mehr merken" : "Merken"
                                    onTriggered: root.saveToggled(slot.a.id)
                                }
                                MenuEntry {
                                    text: "Original im Browser öffnen"
                                    onTriggered: root.originalRequested(slot.a.link)
                                }
                                MenuSeparator {
                                    contentItem: Rectangle {
                                        implicitHeight: 1
                                        color: Theme.hairline
                                    }
                                }
                                MenuEntry {
                                    text: "Einordnen unter Tests"
                                    enabled: slot.a.rubric !== "Tests"
                                    onTriggered: root.rubricChosen(slot.a.id, "Tests")
                                }
                                MenuEntry {
                                    text: "Einordnen unter Reviews"
                                    enabled: slot.a.rubric !== "Reviews"
                                    onTriggered: root.rubricChosen(slot.a.id, "Reviews")
                                }
                                MenuEntry {
                                    text: "Einordnen unter News"
                                    enabled: slot.a.rubric !== "News"
                                    onTriggered: root.rubricChosen(slot.a.id, "News")
                                }
                                MenuEntry {
                                    text: "Einordnen unter Artikel"
                                    enabled: slot.a.rubric !== "Artikel"
                                    onTriggered: root.rubricChosen(slot.a.id, "Artikel")
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------ Noch leer
    Component {
        id: empty
        Item {
            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width, 520)
                spacing: 14
                Label {
                    Layout.alignment: Qt.AlignHCenter
                    text: root.hasSources ? (root.loading ? "Die Ausgabe wird gedruckt …" : "Noch keine Artikel")
                                          : "Willkommen bei Creative Magazin"
                    color: Theme.text
                    font.pixelSize: 26
                    font.bold: true
                }
                Hint {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.hasSources
                          ? "Sobald deine Seiten neue Artikel veröffentlichen, erscheinen sie hier – jeden Tag als neue Ausgabe."
                          : "Füge deine Lieblingsseiten hinzu. Jeden Tag erscheint dann eine neue Ausgabe mit ihren Tests, Reviews, News und Artikeln."
                }
                CButton {
                    Layout.alignment: Qt.AlignHCenter
                    visible: !root.hasSources
                    primary: true
                    text: "Quellen hinzufügen"
                    onClicked: root.addSources()
                }
            }
        }
    }
}
