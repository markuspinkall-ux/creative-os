// Tasks – läuft dauerhaft in KWin.
//  1. Meldet der Gibeon-Taskleiste bei jeder Änderung alle offenen Fenster
//     (welche App, auf welchem Monitor, minimiert, aktiv).
//  2. Stellt die Windows-Tastenkürzel bereit.

const SERVICE = "org.creativeos.Shell";
const PATH = "/Shell";
const IFACE = "org.creativeos.Shell";

function relevant(w) {
    return w.normalWindow && !w.skipTaskbar;
}

function snapshot() {
    const active = workspace.activeWindow;
    const windows = [];
    const order = workspace.stackingOrder || [];
    for (const w of workspace.windowList()) {
        if (!relevant(w)) continue;
        const g = w.frameGeometry;
        windows.push({
            pid: w.pid || 0,
            geo: g ? [g.x, g.y, g.width, g.height] : [0, 0, 0, 0],
            z: order.indexOf(w),
            id: w.internalId.toString(),
            app: w.desktopFileName || "",
            cls: w.resourceClass || "",
            title: w.caption || "",
            output: w.output ? w.output.name : "",
            minimized: !!w.minimized,
            active: w === active,
        });
    }
    return JSON.stringify({
        windows: windows,
        activeOutput: workspace.activeScreen ? workspace.activeScreen.name : "",
    });
}

function push() {
    callDBus(SERVICE, PATH, IFACE, "update", snapshot());
}

function call(method, arg) {
    if (arg === undefined) callDBus(SERVICE, PATH, IFACE, method);
    else callDBus(SERVICE, PATH, IFACE, method, arg);
}

function watch(w) {
    w.captionChanged.connect(push);
    w.minimizedChanged.connect(push);
    w.outputChanged.connect(push);
    // Fensterpositionen (für „Fenster aufnehmen“ in Shots)
    if (w.interactiveMoveResizeFinished) w.interactiveMoveResizeFinished.connect(push);
    if (w.maximizedChanged) w.maximizedChanged.connect(push);
    if (w.fullScreenChanged) w.fullScreenChanged.connect(push);
}

workspace.windowList().forEach(watch);
// Neue Browserfenster (auch ein herausgezogener Tab) erscheinen auf dem Bildschirm mit dem
// Mauszeiger – unter Wayland kann der Browser seine Position nicht selbst bestimmen.
function placeUnderMouse(w) {
    if (!w || !w.normalWindow || w.fullScreen || !workspace.screenAt) return;
    const cls = (w.resourceClass || "").toString().toLowerCase();
    if (cls !== "creative-browser") return;
    const out = workspace.screenAt(workspace.cursorPos);
    if (!out || w.output === out) return;
    const a = workspace.clientArea(KWin.PlacementArea, out, workspace.currentDesktop);
    const g = w.frameGeometry;
    const width = Math.min(g.width, a.width), height = Math.min(g.height, a.height);
    w.frameGeometry = { x: a.x + Math.round((a.width - width) / 2), y: a.y + Math.round((a.height - height) / 2),
                        width: width, height: height };
}

workspace.windowAdded.connect(function (w) { placeUnderMouse(w); watch(w); push(); });
workspace.windowRemoved.connect(push);
workspace.windowActivated.connect(push);

// ---- Windows-Tastenkürzel --------------------------------------------------
// (Die Windows-Taste allein öffnet das Startmenü – das ist in kwinrc unter
//  ModifierOnlyShortcuts eingetragen. Win+Pfeile und Alt+Tab bringt KWin mit.)
registerShortcut("Creative Dateien",   // Kennung bleibt (gespeicherte Tastenkürzel)
     "Gibeon OS: Dateien öffnen", "Meta+E",
                 function () { call("launchRole", "files"); });
registerShortcut("Creative Einstellungen",   // Kennung bleibt (gespeicherte Tastenkürzel)
     "Gibeon OS: Einstellungen öffnen", "Meta+I",
                 function () { call("openSettings"); });
registerShortcut("Creative Sperren",   // Kennung bleibt (gespeicherte Tastenkürzel)
     "Gibeon OS: Bildschirm sperren", "Meta+L",
                 function () { call("lock"); });
registerShortcut("Creative Bildschirmfoto",   // Kennung bleibt (gespeicherte Tastenkürzel)
     "Gibeon OS: Bildschirmausschnitt aufnehmen", "Meta+Shift+S",
                 function () { call("screenshot"); });
registerShortcut("Creative Druck",   // Kennung bleibt (gespeicherte Tastenkürzel)
     "Gibeon OS: Bildschirmfoto (Druck-Taste)", "Print",
                 function () { call("screenshot"); });
registerShortcut("Creative Aufgaben-Manager",   // Kennung bleibt (gespeicherte Tastenkürzel)
     "Gibeon OS: Taskmanager", "Ctrl+Shift+Escape",
                 function () { call("taskManager"); });
registerShortcut("Taskmanager Strg-Alt-Entf", "Gibeon OS: Taskmanager (Strg+Alt+Entf)", "Ctrl+Alt+Del",
                 function () { call("taskManager"); });
registerShortcut("Desktop", "Gibeon OS: Desktop anzeigen", "Meta+D",
                 function () { workspace.showingDesktop = !workspace.showingDesktop; });

push();
