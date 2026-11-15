// Test: jede neue Fensterkennung ausgeben (desktopFileName = Wayland app_id)
function show(w) { print("FENSTER app=" + (w.desktopFileName || "") + " class=" + (w.resourceClass || "") + " titel=" + (w.caption || "")); }
workspace.windowList().forEach(show);
workspace.windowAdded.connect(function (w) {
    show(w);
    w.captionChanged.connect(function () { show(w); });
});
