// Führt shell/kwin/gibeon-fenster/contents/code/main.js mit nachgebauter KWin-Umgebung aus:
// Öffnen (aus Startmenü/Taskleiste), Minimieren, Wiederherstellen, Schließen – ohne Fehler,
// und die Animation startet am richtigen Ort.
const fs = require("fs");
const vm = require("vm");
const path = process.argv[2];
function sig() { const l = []; const f = (...a) => l.forEach(x => x(...a)); f.connect = x => l.push(x); return f; }
const anims = [];
const cfg = { Tasten: JSON.stringify([{ n: ["org.kde.dolphin", "dolphin"], x: 300, y: 975 }]), Start: `40,900,${Date.now()}` };
const ctx = {
    Effect: { Scale: 1, Translation: 2, Opacity: 3, WindowAddedGrabRole: 10, WindowClosedGrabRole: 11, Forward: 0, Backward: 1 },
    QEasingCurve: { OutCubic: 1, InQuad: 2, InOutCubic: 3 },
    animationTime: (d) => d,
    animate: (o) => { anims.push(o); return anims.length; },
    cancel: () => true, redirect: () => false,
    effect: { readConfig: (k, d) => (k in cfg ? cfg[k] : d), configChanged: sig(), grab: () => true, isGrabbed: () => false },
    effects: { hasActiveFullScreenEffect: false, windowAdded: sig(), windowClosed: sig(), windowDataChanged: sig(), stackingOrder: [] },
    Date, JSON, String, Math, console,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path, "utf8"), ctx);
function win(cls) {
    return { windowClass: cls, normalWindow: true, visible: true, minimized: false,
             frameGeometry: { x: 400, y: 200, width: 800, height: 600 }, minimizedChanged: sig() };
}
const a = win("dolphin org.kde.dolphin");
ctx.effects.windowAdded(a);              // aus dem Startmenü (gerade geklickt)
const t1 = anims[0].animations.find(x => x.type === 2).from;
if (t1.value1 !== 40 - 800 || t1.value2 !== 900 - 500) throw new Error("Start nicht aus dem Startmenü: " + JSON.stringify(t1));
const b = win("dolphin org.kde.dolphin");
ctx.effects.windowAdded(b);              // zweites Fenster: aus dem Taskleisten-Symbol
const t2 = anims[1].animations.find(x => x.type === 2).from;
if (t2.value1 !== 300 - 800 || t2.value2 !== 975 - 500) throw new Error("Start nicht aus der Taskleiste: " + JSON.stringify(t2));
b.minimized = true; b.minimizedChanged();
const t3 = anims[2].animations.find(x => x.type === 2).to;
if (t3.value1 !== 300 - 800) throw new Error("Minimieren nicht ins Symbol");
b.minimized = false; b.minimizedChanged();
ctx.effects.windowClosed(a);
if (anims.length !== 5) throw new Error("erwartet 5 Animationen, waren " + anims.length);
console.log("Effekt-Probe: in Ordnung");
