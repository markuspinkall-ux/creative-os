// Creative Tasks – läuft dauerhaft in KWin.
//  1. Meldet der Creative-Taskleiste bei jeder Änderung alle offenen Fenster
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
    // Fensterpositionen (für „Fenster aufnehmen“ in Creative Shots)
    if (w.interactiveMoveResizeFinished) w.interactiveMoveResizeFinished.connect(push);
    if (w.maximizedChanged) w.maximizedChanged.connect(push);
    if (w.fullScreenChanged) w.fullScreenChanged.connect(push);
}

workspace.windowList().forEach(watch);
workspace.windowAdded.connect(function (w) { watch(w); push(); });
workspace.windowRemoved.connect(push);
workspace.windowActivated.connect(push);

// ---- Windows-Tastenkürzel --------------------------------------------------
// (Die Windows-Taste allein öffnet das Startmenü – das ist in kwinrc unter
//  ModifierOnlyShortcuts eingetragen. Win+Pfeile und Alt+Tab bringt KWin mit.)
registerShortcut("Creative Dateien", "Creative OS: Dateien öffnen", "Meta+E",
                 function () { call("launchRole", "files"); });
registerShortcut("Creative Einstellungen", "Creative OS: Einstellungen öffnen", "Meta+I",
                 function () { call("openSettings"); });
registerShortcut("Creative Sperren", "Creative OS: Bildschirm sperren", "Meta+L",
                 function () { call("lock"); });
registerShortcut("Creative Bildschirmfoto", "Creative OS: Bildschirmausschnitt aufnehmen", "Meta+Shift+S",
                 function () { call("screenshot"); });
registerShortcut("Creative Druck", "Creative OS: Bildschirmfoto (Druck-Taste)", "Print",
                 function () { call("screenshot"); });
registerShortcut("Creative Aufgaben-Manager", "Creative OS: Taskmanager", "Ctrl+Shift+Escape",
                 function () { call("taskManager"); });
registerShortcut("Creative Desktop", "Creative OS: Desktop anzeigen", "Meta+D",
                 function () { workspace.showingDesktop = !workspace.showingDesktop; });

push();
