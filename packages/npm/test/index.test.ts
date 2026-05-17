import { describe, expect, it } from "vitest";
import { PACKAGE, banner } from "../src/index.js";

describe("scaffold", () => {
  it("exposes the package name", () => {
    expect(PACKAGE).toBe("henry-castillo");
  });
  it("renders a banner with the version", () => {
    expect(banner("1.2.3")).toContain("henry-castillo 1.2.3");
  });
});
