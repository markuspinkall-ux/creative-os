// Abstand – maximierte Fenster mit kleinem Abstand und runden Ecken.
//
// Ein „echt“ maximiertes Fenster füllt den Bildschirm bis an die Taskleiste, und der Fensterrahmen
// schaltet die runden Ecken ab. Stattdessen legt dieses Skript das Fenster auf die volle Fläche
// minus einen kleinen Rand (GAP) – als normales Fenster, also mit runden Ecken an allen vier Seiten.
// Nochmal maximieren (Knopf, Doppelklick auf die Titelleiste, Win+Pfeil hoch) stellt die alte Größe
// wieder her. Vollbild (F11, Spiele, Videos) bleibt randlos.
//
// Einstellbar in kwinrc: [Script-creative-abstand] gap=6 (0 = aus)

const GAP = Math.max(0, Math.min(40, Number(readConfig("gap", 6)) || 0));
const gapped = new Map();     // Fenster → Größe vor dem „Maximieren“
const normal = new Map();     // Fenster → letzte normale Größe
let busy = false;

function eligible(w) {
    return GAP > 0 && w && w.normalWindow && w.resizeable && !w.fullScreen && !w.specialWindow
        && !w.transient && !w.popupWindow;
}

function area(w) {
    return workspace.clientArea(KWin.MaximizeArea, w);
}

function rect(g) {
    return { x: Math.round(g.x), y: Math.round(g.y), width: Math.round(g.width), height: Math.round(g.height) };
}

function fullyMaximized(w) {
    if (typeof w.maximizeMode === "number") return w.maximizeMode === 3;   // MaximizeFull
    const a = area(w);
    const g = w.frameGeometry;
    return g.x === a.x && g.y === a.y && g.width === a.width && g.height === a.height;
}

function same(a, b) {
    return Math.round(a.x) === Math.round(b.x) && Math.round(a.y) === Math.round(b.y)
        && Math.round(a.width) === Math.round(b.width) && Math.round(a.height) === Math.round(b.height);
}

// Größe, die gerade nur vom Maximieren kommt (der Zustand wird manchmal erst danach gemeldet)
function transient(w) {
    const g = w.frameGeometry;
    return fullyMaximized(w) || same(g, area(w)) || same(g, gapRect(w));
}

function gapRect(w) {
    const a = area(w);
    return { x: a.x + GAP, y: a.y + GAP, width: a.width - 2 * GAP, height: a.height - 2 * GAP };
}

function fallbackNormal(w) {
    const a = area(w);
    const width = Math.round(a.width * 0.7);
    const height = Math.round(a.height * 0.75);
    return { x: a.x + Math.round((a.width - width) / 2), y: a.y + Math.round((a.height - height) / 2), width: width, height: height };
}

function onMaximized(w) {
    if (busy || !eligible(w) || !fullyMaximized(w)) return;
    busy = true;
    try {
        w.setMaximize(false, false);
        if (gapped.has(w)) {
            // zweites Mal maximieren = wiederherstellen
            const before = gapped.get(w);
            gapped.delete(w);
            w.frameGeometry = before;
        } else {
            gapped.set(w, normal.get(w) || fallbackNormal(w));
            w.frameGeometry = gapRect(w);
        }
    } finally {
        busy = false;
    }
}

function watch(w) {
    if (!w || !w.normalWindow) return;
    if (!transient(w)) normal.set(w, rect(w.frameGeometry));
    w.frameGeometryChanged.connect(function () {
        if (busy || gapped.has(w) || w.fullScreen || transient(w)) return;
        normal.set(w, rect(w.frameGeometry));
    });
    if (w.maximizedChanged) w.maximizedChanged.connect(function () { onMaximized(w); });
    // Verschiebt oder zieht man ein „maximiertes“ Fenster, ist es wieder ein normales Fenster
    if (w.interactiveMoveResizeStarted) w.interactiveMoveResizeStarted.connect(function () { gapped.delete(w); });
    // Monitor gewechselt oder Taskleiste verändert: Fläche neu berechnen
    w.outputChanged.connect(function () { if (gapped.has(w)) { busy = true; w.frameGeometry = gapRect(w); busy = false; } });
    if (fullyMaximized(w)) onMaximized(w);     // startet schon maximiert
}

workspace.windowList().forEach(watch);
workspace.windowAdded.connect(watch);
workspace.windowRemoved.connect(function (w) { gapped.delete(w); normal.delete(w); });
if (workspace.screensChanged) workspace.screensChanged.connect(function () {
    gapped.forEach(function (_v, w) { busy = true; w.frameGeometry = gapRect(w); busy = false; });
});
