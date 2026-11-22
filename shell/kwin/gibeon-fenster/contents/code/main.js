// Gibeon OS: Fenster öffnen sich dynamisch.
// Beim Öffnen wächst ein Fenster aus dem Symbol, auf das geklickt wurde (Startmenü oder
// Taskleiste), beim Minimieren schrumpft es in sein Taskleisten-Symbol zurück und kommt
// beim Wiederherstellen von dort wieder heraus. Schließen: kurz kleiner werden und ausblenden.
//
// Wo die Symbole liegen, schreibt die Gibeon-Shell in die Einstellungen dieses Effekts
// (kwinrc, Gruppe [Effect-gibeon-fenster]) und lädt ihn dann neu:
//   Tasten = [{"n": ["org.kde.dolphin", "dolphin"], "x": 512, "y": 1050}, …]   Taskleiste
//   Start  = "x,y,zeit"                                                         letzter Start aus dem Startmenü
"use strict";

var gibeon = {
    tasten: [],
    start: null,

    loadConfig: function () {
        gibeon.dauer = animationTime(300);
        gibeon.dauerZu = animationTime(180);
        try {
            gibeon.tasten = JSON.parse(effect.readConfig("Tasten", "[]")) || [];
        } catch (e) {
            gibeon.tasten = [];
        }
        var s = String(effect.readConfig("Start", "")).split(",");
        gibeon.start = s.length === 3 ? { x: +s[0], y: +s[1], t: +s[2] } : null;
    },

    passend: function (w) {
        if (effects.hasActiveFullScreenEffect) return false;
        if (!w || w.desktopWindow || w.dock || w.popupWindow || w.outline || w.lockScreen) return false;
        if (w.specialWindow || w.splash || w.toolbar || w.utility) return false;
        if (w.skipsCloseAnimation) return false;
        return !!(w.normalWindow || w.dialog);
    },

    namen: function (w) {
        var out = [];
        var add = function (v) {
            v = String(v || "").toLowerCase().replace(/\.desktop$/, "");
            if (v && out.indexOf(v) < 0) out.push(v);
        };
        String(w.windowClass || "").split(" ").forEach(add);
        add(w.desktopFileName);
        return out;
    },

    // Mitte des Taskleisten-Symbols dieses Programms (oder null)
    taste: function (w) {
        var namen = gibeon.namen(w);
        for (var i = 0; i < gibeon.tasten.length; i++) {
            var t = gibeon.tasten[i];
            var n = t.n || [];
            for (var a = 0; a < namen.length; a++) {
                for (var b = 0; b < n.length; b++) {
                    var x = namen[a], y = String(n[b]);
                    if (x === y || x.endsWith("." + y) || y.endsWith("." + x)) {
                        return { x: t.x, y: t.y };
                    }
                }
            }
        }
        return null;
    },

    rect: function (w) {
        return w.frameGeometry || w.geometry;
    },

    // Startpunkt fürs Öffnen: Startmenü (gerade geklickt) → Taskleiste → unten Mitte
    quelle: function (w) {
        var s = gibeon.start;
        if (s && Date.now() - s.t < 8000) {
            gibeon.start = null;           // gilt nur für das nächste neue Fenster
            return { x: s.x, y: s.y };
        }
        var t = gibeon.taste(w);
        if (t) return t;
        var r = gibeon.rect(w);
        return { x: r.x + r.width / 2, y: r.y + r.height };
    },

    weg: function (w, p) {
        var r = gibeon.rect(w);
        return { value1: p.x - (r.x + r.width / 2), value2: p.y - (r.y + r.height / 2) };
    },

    beiOeffnen: function (w) {
        gibeon.beobachten(w);
        if (!gibeon.passend(w) || !w.visible) return;
        if (!effect.grab(w, Effect.WindowAddedGrabRole)) return;
        var p = gibeon.quelle(w);
        w.gibeonAuf = animate({
            window: w,
            curve: QEasingCurve.OutCubic,
            duration: gibeon.dauer,
            animations: [
                { type: Effect.Scale, from: 0.12, to: 1.0 },
                { type: Effect.Translation, from: gibeon.weg(w, p), to: { value1: 0, value2: 0 } },
                { type: Effect.Opacity, from: 0.0, to: 1.0 }
            ]
        });
    },

    beiSchliessen: function (w) {
        if (!gibeon.passend(w) || !w.visible || w.minimized) return;
        if (!effect.grab(w, Effect.WindowClosedGrabRole)) return;
        if (w.gibeonAuf) { cancel(w.gibeonAuf); delete w.gibeonAuf; }
        w.gibeonZu = animate({
            window: w,
            curve: QEasingCurve.InQuad,
            duration: gibeon.dauerZu,
            animations: [
                { type: Effect.Scale, to: 0.9 },
                { type: Effect.Opacity, to: 0.0 }
            ]
        });
    },

    beiMinimieren: function (w) {
        if (effects.hasActiveFullScreenEffect || !gibeon.passend(w)) return;
        if (w.gibeonHoch) {
            if (redirect(w.gibeonHoch, Effect.Backward)) return;
            cancel(w.gibeonHoch); delete w.gibeonHoch;
        }
        if (w.gibeonRunter) {
            if (redirect(w.gibeonRunter, Effect.Forward)) return;
            cancel(w.gibeonRunter);
        }
        var p = gibeon.taste(w);
        if (!p) { var r = gibeon.rect(w); p = { x: r.x + r.width / 2, y: r.y + r.height + 40 }; }
        w.gibeonRunter = animate({
            window: w,
            curve: QEasingCurve.InOutCubic,
            duration: gibeon.dauer,
            animations: [
                { type: Effect.Scale, from: 1.0, to: 0.08 },
                { type: Effect.Translation, from: { value1: 0, value2: 0 }, to: gibeon.weg(w, p) },
                { type: Effect.Opacity, from: 1.0, to: 0.0 }
            ]
        });
    },

    beiWiederherstellen: function (w) {
        if (effects.hasActiveFullScreenEffect || !gibeon.passend(w)) return;
        if (w.gibeonRunter) {
            if (redirect(w.gibeonRunter, Effect.Backward)) return;
            cancel(w.gibeonRunter); delete w.gibeonRunter;
        }
        if (w.gibeonHoch) {
            if (redirect(w.gibeonHoch, Effect.Forward)) return;
            cancel(w.gibeonHoch);
        }
        var p = gibeon.taste(w);
        if (!p) { var r = gibeon.rect(w); p = { x: r.x + r.width / 2, y: r.y + r.height + 40 }; }
        w.gibeonHoch = animate({
            window: w,
            curve: QEasingCurve.OutCubic,
            duration: gibeon.dauer,
            animations: [
                { type: Effect.Scale, from: 0.08, to: 1.0 },
                { type: Effect.Translation, from: gibeon.weg(w, p), to: { value1: 0, value2: 0 } },
                { type: Effect.Opacity, from: 0.0, to: 1.0 }
            ]
        });
    },

    // KWin 6 meldet Minimieren am Fenster selbst (ältere Versionen über effects)
    beobachten: function (w) {
        if (!w || w.gibeonBeobachtet || effects.windowMinimized) return;
        if (!w.minimizedChanged) return;
        w.gibeonBeobachtet = true;
        w.minimizedChanged.connect(function () {
            if (w.minimized) gibeon.beiMinimieren(w);
            else gibeon.beiWiederherstellen(w);
        });
    },

    datenGeaendert: function (w, rolle) {
        if (rolle === Effect.WindowAddedGrabRole && w.gibeonAuf && effect.isGrabbed(w, rolle)) {
            cancel(w.gibeonAuf); delete w.gibeonAuf;
        } else if (rolle === Effect.WindowClosedGrabRole && w.gibeonZu && effect.isGrabbed(w, rolle)) {
            cancel(w.gibeonZu); delete w.gibeonZu;
        }
    },

    init: function () {
        gibeon.loadConfig();
        effect.configChanged.connect(gibeon.loadConfig);
        effects.windowAdded.connect(gibeon.beiOeffnen);
        effects.windowClosed.connect(gibeon.beiSchliessen);
        effects.windowDataChanged.connect(gibeon.datenGeaendert);
        if (effects.windowMinimized) {
            effects.windowMinimized.connect(gibeon.beiMinimieren);
            effects.windowUnminimized.connect(gibeon.beiWiederherstellen);
        } else {
            (effects.stackingOrder || []).forEach(gibeon.beobachten);
        }
    }
};

gibeon.init();
