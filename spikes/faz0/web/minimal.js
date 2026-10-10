// Tells Python the page is up and the bridge works; used for startup timing.
window.addEventListener("pywebviewready", () => window.pywebview.api.ready());
