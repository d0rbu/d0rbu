/**
 * Scaffold entrypoint for the henry-castillo npm wrapper.
 * Milestone 4 replaces this with a launcher that execs the bundled binary.
 */
import { realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const PACKAGE = "henry-castillo";

export function banner(version = "0.0.0"): string {
  return `${PACKAGE} ${version} — scaffold (npm wrapper wired in Milestone 4)`;
}

/**
 * True when this module is the process entry point.
 *
 * npm-installed `bin` symlinks make `import.meta.url` the realpath of the
 * file while `process.argv[1]` is the symlink path, so a raw string compare
 * never matches — both sides must be resolved with `realpathSync` first.
 *
 * `moduleUrl`/`argv` are parameters (defaulted to the real globals) so the
 * guard logic is unit-testable by passing explicit inputs — no global
 * mutation required. Production callers use `isMain()` with no arguments.
 * `argv` (not `arg`) is the injection point so a test can supply an array
 * with no entry point without the default-parameter rule swapping it back
 * to `process.argv`.
 */
export function isMain(
  moduleUrl: string = import.meta.url,
  argv: readonly string[] = process.argv,
): boolean {
  const arg = argv[1];
  if (!arg) {
    return false;
  }
  try {
    return realpathSync(fileURLToPath(moduleUrl)) === realpathSync(arg);
  } catch {
    return false;
  }
}

if (isMain()) {
  console.log(banner());
}
