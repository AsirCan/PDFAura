// Runs while the page parses, before pywebview injects its bridge.
window.__evalEarly = (() => { try { return eval("1") === 1 ? "allowed" : "?"; } catch (e) { return "blocked"; } })();
