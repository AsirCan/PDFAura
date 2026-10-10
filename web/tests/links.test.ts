import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { keepLinksOutside } from "../src/lib/links";

describe("links", () => {
  let stop: () => void;
  let opened: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    stop = keepLinksOutside(document);
    opened = vi.spyOn(window, "open").mockImplementation(() => null);
  });
  afterEach(() => {
    stop();
    opened.mockRestore();
    document.body.innerHTML = "";
  });

  function click(href: string) {
    const link = document.createElement("a");
    link.href = href;
    link.innerHTML = "<span>x</span>";
    document.body.append(link);
    const event = new MouseEvent("click", { bubbles: true, cancelable: true });
    link.querySelector("span")!.dispatchEvent(event);
    return event;
  }

  it("sends a web link to the system browser instead of leaving the app", () => {
    const event = click("https://github.com/AsirCan/PDFAura");
    expect(event.defaultPrevented).toBe(true);
    expect(opened).toHaveBeenCalledWith("https://github.com/AsirCan/PDFAura", "_blank", "noopener");
  });

  it("ignores links to anything but the web", () => {
    for (const href of ["file:///C:/Windows/System32/calc.exe", "ms-settings:privacy"]) {
      expect(click(href).defaultPrevented).toBe(true);
    }
    expect(opened).not.toHaveBeenCalled();
  });

  it("leaves the app's own links alone", () => {
    expect(click("#settings").defaultPrevented).toBe(false);
    expect(opened).not.toHaveBeenCalled();
  });
});
