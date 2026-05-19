import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";
import { banner, isMain, PACKAGE } from "../src/index.js";

const SUFFIX = "— scaffold (npm wrapper wired in Milestone 4)";
const THIS_FILE = resolve(import.meta.dirname, "index.test.ts");
const THIS_URL = pathToFileURL(THIS_FILE).href;

describe("scaffold", () => {
  it("exposes the package name", () => {
    expect(PACKAGE).toBe("henry-castillo");
  });

  it("renders a banner with the version", () => {
    expect(banner("1.2.3")).toBe(`henry-castillo 1.2.3 ${SUFFIX}`);
  });

  it("defaults the version to 0.0.0", () => {
    expect(banner()).toBe(`henry-castillo 0.0.0 ${SUFFIX}`);
  });

  it("passes a pre-release version through verbatim", () => {
    expect(banner("1.0.0-rc.1")).toBe(`henry-castillo 1.0.0-rc.1 ${SUFFIX}`);
  });

  it("does not validate the version (empty string passes through)", () => {
    expect(banner("")).toBe(`henry-castillo  ${SUFFIX}`);
  });

  describe("isMain", () => {
    it("returns false when argv has no entry point", () => {
      expect(isMain(THIS_URL, ["node"])).toBe(false);
    });

    it("returns true when the resolved module path equals argv[1]", () => {
      expect(isMain(THIS_URL, ["node", THIS_FILE])).toBe(true);
    });

    it("returns false when the resolved paths differ", () => {
      expect(isMain(THIS_URL, ["node", import.meta.dirname])).toBe(false);
    });

    it("returns false when a path cannot be resolved (realpath throws)", () => {
      const missing = resolve(import.meta.dirname, "does-not-exist-xyz");
      expect(isMain(pathToFileURL(missing).href, ["node", missing])).toBe(
        false,
      );
    });
  });

  it("prints the banner when executed as the entry point", () => {
    const dist = resolve(import.meta.dirname, "../dist/index.js");
    const r = spawnSync(process.execPath, [dist], { encoding: "utf8" });
    expect(r.status).toBe(0);
    expect(r.stdout.trim()).toBe(
      "henry-castillo 0.0.0 — scaffold (npm wrapper wired in Milestone 4)",
    );
    expect(r.stderr).toBe("");
  });
});
