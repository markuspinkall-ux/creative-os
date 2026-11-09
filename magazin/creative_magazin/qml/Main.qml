import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Creative

ApplicationWindow {
    id: window
    width: 1280
    height: 820
    minimumWidth: 860
    minimumHeight: 600
    visible: true
    color: Theme.ground
    title: "Creative Magazin"
    font.family: Theme.fontFamily
    palette.windowText: Theme.text
    palette.text: Theme.text

    required property QtObject magazine
    property bool selftest: false

    property string view: "magazine"
    property int page: 0
    property int pendingPage: 0
    property int direction: 1
    readonly property var rubricOrder: ["Tests", "Reviews", "News", "Artikel"]
    readonly property var pages: buildPages(magazine.articles)
    readonly property var order: readingOrder(pages)
    readonly property bool spread: pageArea.width >= 1100
    readonly property int step: spread ? 2 : 1
    readonly property bool readerOpen: reader.open

    // Heft zusammenstellen: Titelseite, Inhalt, dann je Rubrik Seiten mit vier Artikeln.
    function buildPages(articles) {
        if (articles.length === 0)
            return [{ kind: "empty" }]
        const result = [{ kind: "cover" }, { kind: "contents", sections: [] }]
        const sections = []
        for (const name of rubricOrder) {
            const items = articles.filter(a => a.rubric === name)
            if (items.length === 0)
                continue
            const entries = []
            for (let i = 0; i < items.length; i += 4) {
                const chunk = items.slice(i, i + 4)
                result.push({ kind: "teasers", rubric: name, items: chunk })
                for (const a of chunk)
                    entries.push({ id: a.id, title: a.title, site: a.site, page: result.length - 1 })
            }
            sections.push({ rubric: name, entries: entries })
        }
        result[1].sections = sections
        return result
    }

    function readingOrder(list) {
        const ids = []
        for (const p of list) {
            if (p.kind === "teasers") {
                for (const a of p.items)
                    ids.push(a.id)
            }
        }
        return ids
    }

    function go(target) {
        if (flip.running)
            return
        let t = Math.max(0, Math.min(target, pages.length - 1))
        if (spread)
            t -= t % 2
        if (t === page)
            return
        direction = t > page ? 1 : -1
        pendingPage = t
        flip.start()
    }

    function next() { go(page + step) }
    function prev() { go(page - step) }

    function showIssue(date) {
        magazine.openIssue(date)
        page = 0
        view = "magazine"
    }

    onPagesChanged: {
        if (page > pages.length - 1)
            page = Math.max(0, pages.length - 1)
        if (spread)
            page -= page % 2
    }
    onSpreadChanged: if (spread) page -= page % 2

    Component.onCompleted: if (magazine.sources.length === 0) view = "sources"

    component Hint: Label {
        color: Theme.textMuted
        font.pixelSize: 13
        elide: Text.ElideRight
        textFormat: Text.PlainText
    }

    Shortcut {
        sequences: ["Right", "PgDown", "Space"]
        enabled: window.view === "magazine" && !window.readerOpen
        onActivated: window.next()
    }
    Shortcut {
        sequences: ["Left", "PgUp", "Backspace"]
        enabled: window.view === "magazine" && !window.readerOpen
        onActivated: window.prev()
    }
    Shortcut {
        sequence: "Home"
        enabled: window.view === "magazine" && !window.readerOpen
        onActivated: window.go(0)
    }
    Shortcut {
        sequence: "End"
        enabled: window.view === "magazine" && !window.readerOpen
        onActivated: window.go(window.pages.length - 1)
    }
    Shortcut {
        sequence: "F5"
        onActivated: window.magazine.refresh()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        // ------------------------------------------------------------ Kopfleiste
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Label {
                text: "Creative Magazin"
                color: Theme.text
                font.pixelSize: 22
                font.bold: true
            }
            Hint {
                Layout.fillWidth: true
                Layout.leftMargin: 8
                text: window.view === "magazine" ? window.magazine.issueLabel : ""
            }
            CButton {
                id: issueButton
                text: "Ausgaben ▾"
                enabled: window.magazine.issues.length > 0
                onClicked: issuesPopup.opened ? issuesPopup.close() : issuesPopup.open()
            }
            CButton {
                text: "Heft"
                primary: window.view === "magazine" && window.magazine.issue !== "gemerkt"
                onClicked: {
                    if (window.magazine.issue === "gemerkt" && window.magazine.issues.length > 0)
                        window.showIssue(window.magazine.issues[0].date)
                    window.view = "magazine"
                }
            }
            CButton {
                text: "Gemerkt"
                primary: window.view === "magazine" && window.magazine.issue === "gemerkt"
                onClicked: window.showIssue("gemerkt")
            }
            CButton {
                text: "Quellen"
                primary: window.view === "sources"
                onClicked: window.view = "sources"
            }
            CButton {
                text: window.magazine.busy === "refresh" ? "Lädt …" : "Aktualisieren"
                enabled: window.magazine.busy === "" && window.magazine.sources.length > 0
                onClicked: window.magazine.refresh()
            }
        }

        // ------------------------------------------------------------ Heft
        Item {
            id: pageArea
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: window.view === "magazine"

            Item {
                id: sheet
                anchors.fill: parent
                transform: Rotation {
                    id: turn
                    origin.x: window.direction > 0 ? 0 : sheet.width
                    origin.y: sheet.height / 2
                    axis.x: 0
                    axis.y: 1
                    axis.z: 0
                    angle: 0
                }

                RowLayout {
                    anchors.fill: parent
                    spacing: 18

                    MagazinePage {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        info: window.pages[window.page] || ({ kind: "blank" })
                        number: window.page
                        articles: window.magazine.articles
                        issueLabel: window.magazine.issueLabel
                        rubricOrder: window.rubricOrder
                        hasSources: window.magazine.sources.length > 0
                        loading: window.magazine.busy !== ""
                        onOpenArticle: key => window.magazine.openArticle(key)
                        onOpenPage: index => window.go(index)
                        onRubricChosen: (key, rubric) => window.magazine.setRubric(key, rubric)
                        onSaveToggled: key => window.magazine.toggleSaved(key)
                        onOriginalRequested: url => window.magazine.openOriginal(url)
                        onAddSources: window.view = "sources"
                    }
                    MagazinePage {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        visible: window.spread && window.pages.length > 1
                        info: window.page + 1 < window.pages.length ? window.pages[window.page + 1] : ({ kind: "blank" })
                        number: window.page + 1
                        articles: window.magazine.articles
                        issueLabel: window.magazine.issueLabel
                        rubricOrder: window.rubricOrder
                        hasSources: window.magazine.sources.length > 0
                        loading: window.magazine.busy !== ""
                        onOpenArticle: key => window.magazine.openArticle(key)
                        onOpenPage: index => window.go(index)
                        onRubricChosen: (key, rubric) => window.magazine.setRubric(key, rubric)
                        onSaveToggled: key => window.magazine.toggleSaved(key)
                        onOriginalRequested: url => window.magazine.openOriginal(url)
                        onAddSources: window.view = "sources"
                    }
                }
            }

            // Mausrad und Touchpad blättern um.
            WheelHandler {
                target: null
                enabled: !window.readerOpen
                property real collected: 0
                onWheel: event => {
                    collected += event.angleDelta.y !== 0 ? event.angleDelta.y : event.angleDelta.x
                    if (collected <= -120) {
                        collected = 0
                        window.next()
                    } else if (collected >= 120) {
                        collected = 0
                        window.prev()
                    }
                }
            }

            // Wischen wie in einer echten Zeitschrift.
            DragHandler {
                target: null
                enabled: !window.readerOpen
                xAxis.enabled: true
                yAxis.enabled: false
                onActiveChanged: {
                    if (active)
                        return
                    if (activeTranslation.x < -90)
                        window.next()
                    else if (activeTranslation.x > 90)
                        window.prev()
                }
            }
        }

        SequentialAnimation {
            id: flip
            ParallelAnimation {
                NumberAnimation { target: sheet; property: "opacity"; to: 0; duration: 150; easing.type: Easing.InQuad }
                NumberAnimation { target: turn; property: "angle"; to: -30 * window.direction; duration: 150; easing.type: Easing.InQuad }
            }
            ScriptAction {
                script: {
                    window.page = window.pendingPage
                    turn.angle = 30 * window.direction
                }
            }
            ParallelAnimation {
                NumberAnimation { target: sheet; property: "opacity"; to: 1; duration: 220; easing.type: Easing.OutQuad }
                NumberAnimation { target: turn; property: "angle"; to: 0; duration: 220; easing.type: Easing.OutQuad }
            }
        }

        // ------------------------------------------------------------ Quellen
        Sources {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: window.view === "sources"
            magazine: window.magazine
            onDone: window.view = "magazine"
        }

        // ------------------------------------------------------------ Fußleiste
        RowLayout {
            Layout.fillWidth: true
            visible: window.view === "magazine"
            spacing: 10

            CButton {
                text: "‹  Zurückblättern"
                enabled: window.page > 0
                onClicked: window.prev()
            }
            Hint {
                text: window.pages.length <= 1 ? ""
                      : window.spread && window.page + 1 < window.pages.length
                        ? "Seite " + (window.page + 1) + "–" + (window.page + 2) + " von " + window.pages.length
                        : "Seite " + (window.page + 1) + " von " + window.pages.length
            }
            CButton {
                text: "Weiterblättern  ›"
                enabled: window.page + window.step < window.pages.length
                onClicked: window.next()
            }
            Hint {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                text: window.magazine.status
            }
        }
    }

    // ------------------------------------------------------------ Ausgaben-Auswahl
    Popup {
        id: issuesPopup
        parent: issueButton
        y: issueButton.height + 6
        x: issueButton.width - width
        width: 320
        height: Math.min(440, issueList.contentHeight + 20)
        padding: 10
        background: Rectangle {
            color: Theme.raised
            radius: Theme.radiusMenu
            border.color: Theme.hairline
        }
        contentItem: ListView {
            id: issueList
            clip: true
            spacing: 2
            model: window.magazine.issues
            ScrollBar.vertical: ScrollBar {}
            delegate: ItemDelegate {
                id: issueRow
                required property var modelData
                width: ListView.view.width
                contentItem: RowLayout {
                    Label {
                        Layout.fillWidth: true
                        text: issueRow.modelData.label
                        color: Theme.text
                        font.pixelSize: 13
                        font.bold: window.magazine.issue === issueRow.modelData.date
                        elide: Text.ElideRight
                    }
                    Label {
                        text: issueRow.modelData.count + " Artikel"
                        color: Theme.textMuted
                        font.pixelSize: 12
                    }
                }
                background: Rectangle {
                    radius: Theme.radiusRow
                    color: window.magazine.issue === issueRow.modelData.date ? Theme.surface
                           : (issueRow.hovered ? Theme.hover : "transparent")
                }
                onClicked: {
                    window.showIssue(issueRow.modelData.date)
                    issuesPopup.close()
                }
            }
        }
    }

    // ------------------------------------------------------------ Artikel lesen
    Reader {
        id: reader
        anchors.fill: parent
        magazine: window.magazine
        order: window.order
    }

    // Selbsttest beim Bauen: einmal durch Heft, Artikel und Quellen.
    Timer {
        id: selftestRun
        property int stage: 0
        running: window.selftest
        interval: 350
        repeat: true
        onTriggered: {
            switch (stage++) {
            case 0: window.view = "magazine"; window.go(2); break
            case 1: window.go(window.pages.length - 1); break
            case 2: window.magazine.openArticle(window.order[0]); break
            case 3: window.magazine.toggleSaved(window.order[0]); break
            case 4: window.magazine.openArticle(window.order[1]); break
            case 5: window.magazine.closeArticle(); window.view = "sources"; break
            case 6: window.width = 900; window.showIssue("gemerkt"); break
            case 7: window.go(1); break
            default: Qt.quit()
            }
        }
    }
}
