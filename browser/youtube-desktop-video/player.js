(() => {
    const host = document.createElement("div");
    const panel = host.attachShadow({ mode: "closed" });
    const style = document.createElement("style");
    style.textContent = `
        :host { position: fixed; left: 16px; bottom: 16px; z-index: 2147483647; }
        :host([hidden]) { display: none; }
        button, output {
            font: 600 13px system-ui, sans-serif;
            color: #f2f4fa;
            background: #1c2029;
            border: 1px solid #606778;
            border-radius: 10px;
            padding: 9px 12px;
        }
        button { cursor: pointer; }
        button:hover { background: #303646; }
        output { display: block; max-width: 280px; margin-bottom: 6px; }
        output:empty { display: none; }
    `;
    const button = document.createElement("button");
    button.type = "button";
    const status = document.createElement("output");
    status.setAttribute("role", "status");
    panel.append(style, status, button);
    document.body.append(host);

    function refresh() {
        host.hidden = location.pathname !== "/watch"
            || !new URLSearchParams(location.search).get("v");
        button.textContent = document.pictureInPictureElement
            ? "Bild-in-Bild schließen" : "Auf Desktop ansehen";
        status.textContent = "";
    }

    button.addEventListener("click", async () => {
        status.textContent = "";
        try {
            if (document.pictureInPictureElement) {
                await document.exitPictureInPicture();
                return;
            }
            const video = document.querySelector("#movie_player video.html5-main-video");
            if (!video || !video.videoWidth) {
                status.textContent = "Starte zuerst das Video.";
                return;
            }
            if (!document.pictureInPictureEnabled) {
                status.textContent = "Bild-in-Bild ist für dieses Video nicht verfügbar.";
                return;
            }
            await video.requestPictureInPicture();
        } catch {
            status.textContent = "Brave konnte das Video nicht in Bild-in-Bild öffnen.";
        }
    });

    document.addEventListener("yt-navigate-finish", refresh);
    document.addEventListener("enterpictureinpicture", refresh, true);
    document.addEventListener("leavepictureinpicture", refresh, true);
    window.addEventListener("popstate", refresh);
    refresh();
})();
