// Shared front-end configuration for the IM pages.
//
// window.API_BASE is the base URL of the backend. Defaults:
//   - "http://localhost:8000" when the pages are opened over file:// or
//     on localhost, where the backend normally runs.
//   - "" (same origin) when the pages are served by the backend or a
//     proxy behind the same origin.
// Set an explicit value before this file loads, or pass ?api_base=<url>.
(function () {
    if (typeof window.API_BASE !== "undefined") return; // set by an earlier script
    const params = new URLSearchParams(window.location.search);
    if (params.has("api_base")) {
        window.API_BASE = params.get("api_base") || "";
        return;
    }
    const local =
        window.location.protocol === "file:" ||
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1" ||
        window.location.hostname === "::1" ||
        window.location.hostname === "[::1]";
    window.API_BASE = local ? "http://localhost:8000" : "";
})();

// Poll the backend health endpoint until the server answers. Browsers
// cannot start the Python backend process themselves; the server should be
// started with start_backend.ps1 / start_backend.bat (or as a Windows
// Service) or manually with: python IM_Backend.py. While waiting, the
// status element (by id) shows why nothing loads.
async function ensureConnected(statusElId) {
    const statusEl = document.getElementById(statusElId);
    const base = String(window.API_BASE || "http://localhost:8000").replace(/\/+$/, "");
    for (;;) {
        try {
            const response = await fetch(`${base}/api/health`);
            if (response.ok) {
                if (statusEl) statusEl.textContent = "Connected.";
                return;
            }
        } catch (error) {
            /* backend not reachable yet */
        }
        if (statusEl) statusEl.textContent = "Waiting for the inventory backend...";
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
}
