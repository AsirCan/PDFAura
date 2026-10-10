import { describe, expect, it } from "vitest";
import { format, language, t } from "../src/lib/i18n.svelte";

describe("strings", () => {
  it("fills in fields the way Python's str.format does", () => {
    expect(format("{pages} sayfa · {size:.2f} MB", { pages: 3, size: 1.23456 })).toBe("3 sayfa · 1.23 MB");
  });

  it("leaves a field it was not given", () => {
    expect(format("Sayfa {current} / {total}", { current: 2 })).toBe("Sayfa 2 / {total}");
  });

  it("shows the key when a string is missing, never nothing", () => {
    language.apply({ language: "tr", rtl: false, strings: { a: "A" } });
    expect(t("a")).toBe("A");
    expect(t("not_there")).toBe("not_there");
  });

  it("lays the page out right to left for Arabic and Urdu", () => {
    language.apply({ language: "ar", rtl: true, strings: {} });
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    language.apply({ language: "tr", rtl: false, strings: {} });
    expect(document.documentElement.dir).toBe("ltr");
  });
});
