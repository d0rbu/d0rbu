/**
 * Scaffold entrypoint for the henry-castillo npm wrapper.
 * Milestone 4 replaces this with a launcher that execs the bundled binary.
 */
export const PACKAGE = "henry-castillo";

export function banner(version = "0.0.0"): string {
  return `${PACKAGE} ${version} — scaffold (npm wrapper wired in Milestone 4)`;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  // eslint-disable-next-line no-console
  console.log(banner());
}
