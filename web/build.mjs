import { cpSync, mkdirSync, rmSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const dist = resolve(__dirname, "dist");

// Remove dist/ if it exists, then recreate it.
rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });
mkdirSync(resolve(dist, "data"), { recursive: true });

// Copy source files into dist/.
cpSync(resolve(__dirname, "index.html"), resolve(dist, "index.html"));
cpSync(
  resolve(__dirname, "data", "card.json"),
  resolve(dist, "data", "card.json"),
);
