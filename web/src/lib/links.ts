// A link never takes the window away from the app (#25, security): one to
// the web opens in the system browser -- pywebview hands window.open to it
// (OPEN_EXTERNAL_LINKS_IN_BROWSER) -- and any other scheme is ignored. The
// page has no links of its own today; this is the rule for any that come.
export function keepLinksOutside(doc: Document = document): () => void {
  const click = (event: MouseEvent) => {
    const link = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
    if (!link) return;
    const url = new URL(link.href, doc.location.href);
    if (url.origin === doc.location.origin) return;
    event.preventDefault();
    if (url.protocol === "https:" || url.protocol === "http:") window.open(url.href, "_blank", "noopener");
  };
  doc.addEventListener("click", click, true);
  return () => doc.removeEventListener("click", click, true);
}
